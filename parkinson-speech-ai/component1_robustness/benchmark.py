"""Benchmark the quality-gate models on the per-clip labels and pick the best one.

Data: results/component1_robustness/gate_labels.csv (built by labels.py).

Protocol (identical for every model):
    1. Hold out a test set of PARTICIPANTS (GroupShuffleSplit, config seed).
    2. On the rest: StratifiedGroupKFold by participant_id (n_folds, config seed).
       The same folds are used for every model.
    3. Per fold: fit on train, predict validation. Metrics = mean +/- std over folds.
    4. Fit on all development rows, evaluate once on the held-out test set.

"Positive" class = UNRELIABLE (the class the gate exists to catch):
    precision / recall / F1      for catching unreliable clips
    false_accept_rate (FAR)      unreliable clips that PASSED   / all unreliable
    false_reject_rate (FRR)      reliable clips that FAILED     / all reliable
    roc_auc                      quality_score ranking reliable above unreliable
    downstream_accuracy          Component 2 accuracy (PD/HC) on the clips the gate PASSED
    pass_rate                    share of clips passed

Selection (config benchmark.selection_order), lexicographic with a tolerance:
    eligible: false_reject_rate <= max_false_reject_rate (a gate rejecting everything has FAR 0)
    then lowest FAR -> highest downstream accuracy -> highest F1 -> fastest (input-cost tier)
    any remaining tie -> the simpler model.

Usage (from parkinson-speech-ai/):
    python -m component1_robustness.benchmark
"""

import json
import re
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import binomtest  # noqa: E402
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold  # noqa: E402

from component1_robustness.config import DEFAULT_CONFIG_PATH, load_config, resolve_path  # noqa: E402
from component1_robustness.gate_models import (  # noqa: E402
    PASS, TRAINABLE, get_gate_model, mfcc_means, save_gate_model,
)
from component1_robustness.labels import LABELS_CSV_NAME, NO_PREDICTION, RELIABLE  # noqa: E402
from component1_robustness.pipeline import json_safe  # noqa: E402
from component1_robustness.quality_metrics import compute_quality  # noqa: E402

METRICS = ["accuracy", "precision", "recall", "f1", "false_accept_rate", "false_reject_rate",
           "roc_auc", "downstream_accuracy", "pass_rate"]
LOWER_IS_BETTER = {"false_accept_rate", "false_reject_rate", "speed"}
COMPLEXITY = {"comp1-A": 0, "comp1-B-logreg": 1, "comp1-B-svm": 2, "comp1-B-rf": 3}
INPUT_COST_TIER = {"comp1-A": 1, "comp1-B-logreg": 2, "comp1-B-svm": 2, "comp1-B-rf": 2}
SNR_CONDITIONS = [("clean", "clean"), ("noise_snr_10db", "10"), ("noise_snr_5db", "5"),
                  ("noise_snr_0db", "0"), ("noise_snr_-5db", "-5")]

BENCHMARK_CSV = "gate_benchmark.csv"
TIMING_CSV = "gate_benchmark_timing.csv"
SNR_PNG = "gate_benchmark_vs_snr.png"
SELECTED_JSON = "selected_gate_model.json"
LABEL_PER_CLIP = "per_clip"


# --- Metrics -------------------------------------------------------------------------

def auc_reliable(reliable: np.ndarray, score: np.ndarray) -> float:
    """ROC-AUC = P(score of a reliable clip > score of an unreliable clip), ties count 1/2.

    Pair-counting (Mann-Whitney) form: exact, and easy to check by hand.
    """
    pos, neg = score[reliable], score[~reliable]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    diff = pos[:, None] - neg[None, :]
    return float(((diff > 0).sum() + 0.5 * (diff == 0).sum()) / (len(pos) * len(neg)))


def _ratio(num: int, den: int) -> float:
    return num / den if den else float("nan")


def _count_metrics(tp: int, fn: int, fp: int, tn: int) -> dict[str, float]:
    """Confusion-matrix metrics. Positive class = unreliable."""
    return {
        "accuracy": _ratio(tp + tn, tp + fn + fp + tn),
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        "false_accept_rate": _ratio(fn, fn + tp),
        "false_reject_rate": _ratio(fp, fp + tn),
    }


def gate_metrics(reliable, passed, score, c2_correct) -> dict[str, float]:
    """All gate metrics for one set of predictions. Positive class = unreliable."""
    reliable, passed = np.asarray(reliable, bool), np.asarray(passed, bool)
    score, c2_correct = np.asarray(score, float), np.asarray(c2_correct, bool)
    unreliable, failed = ~reliable, ~passed
    tp = int((unreliable & failed).sum())   # unreliable, caught
    fn = int((unreliable & passed).sum())   # unreliable, let through (false accept)
    fp = int((reliable & failed).sum())     # reliable, rejected (false reject)
    tn = int((reliable & passed).sum())     # reliable, passed
    return {
        **_count_metrics(tp, fn, fp, tn),
        "roc_auc": auc_reliable(reliable, score),
        "downstream_accuracy": _ratio(int(c2_correct[passed].sum()), int(passed.sum())),
        "pass_rate": _ratio(int(passed.sum()), len(passed)),
    }


def mcnemar(correct_a, correct_b) -> dict:
    """Exact McNemar test: do two models make different errors on the same clips?"""
    a, b = np.asarray(correct_a, bool), np.asarray(correct_b, bool)
    only_a, only_b = int((a & ~b).sum()), int((~a & b).sum())
    n = only_a + only_b
    p = 1.0 if n == 0 else float(binomtest(only_a, n, 0.5).pvalue)
    return {"only_first_correct": only_a, "only_second_correct": only_b, "p_value": p}


# --- Data and splits ---------------------------------------------------------------------

def load_labels(config: dict) -> pd.DataFrame | None:
    """gate_labels.csv with helper columns; None (with a message) if it does not exist."""
    path = resolve_path(config, "results") / LABELS_CSV_NAME
    if not path.is_file():
        print(f"Label table not found: {path}\nBuild it first: python -m component1_robustness.labels")
        return None
    table = pd.read_csv(path).reset_index(drop=True)
    table["reliable"] = table["label"] == RELIABLE
    truth = (table["group"] == "PD").astype(int)
    table["c2_correct"] = (table["degraded_prediction"] != NO_PREDICTION) & (table["degraded_prediction"] == truth)
    return table


def make_splits(table: pd.DataFrame, config: dict):
    """(dev_index, test_index, folds) with no participant on both sides of any split."""
    bench, seed = config["benchmark"], config["seed"]
    groups = table["participant_id"].to_numpy()
    outer = GroupShuffleSplit(n_splits=1, test_size=bench["test_fraction"], random_state=seed)
    dev_pos, test_pos = next(outer.split(table, groups=groups))
    dev = table.iloc[dev_pos]
    n_folds = min(bench["n_folds"], dev["participant_id"].nunique())
    inner = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    folds = [(dev.index[tr].to_numpy(), dev.index[va].to_numpy())
             for tr, va in inner.split(dev, dev["reliable"], dev["participant_id"])]
    return dev.index.to_numpy(), table.index[test_pos].to_numpy(), folds


# --- Evaluation ----------------------------------------------------------------------------

def _eval_config(config: dict) -> dict:
    """Config used for gate decisions in the benchmark (duration rule optional, see config)."""
    if config["benchmark"]["apply_duration_rule"]:
        return config
    return dict(config, min_duration_s=0.0, max_duration_s=float("inf"))


def _predict_rows(model, rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, float]:
    """(passed, score 0-1, mean seconds per prediction) for every row."""
    passed, score = [], []
    start = time.perf_counter()
    for quality in rows.to_dict(orient="records"):
        result = model.predict(quality)
        passed.append(result["decision"] == PASS)
        score.append(result["quality_score"] / 100.0)
    seconds = (time.perf_counter() - start) / max(len(rows), 1)
    return np.array(passed), np.array(score), seconds


def _metrics_for(table: pd.DataFrame, index, passed, score) -> dict:
    rows = table.loc[index]
    return gate_metrics(rows["reliable"], passed, score, rows["c2_correct"])


def _fit(name: str, config: dict, table: pd.DataFrame, index):
    """A new gate model of this name, trained on the given rows."""
    return get_gate_model(name, config).fit(table.loc[index], table.loc[index, "label"],
                                            table.loc[index, "participant_id"])


def evaluate_model(name, table, dev_index, test_index, folds, config) -> dict:
    """CV fold metrics, out-of-fold predictions and held-out test metrics for one model."""
    cfg = _eval_config(config)
    fold_metrics, oof, predict_times = [], [], []
    for train_idx, val_idx in folds:
        model = _fit(name, cfg, table, train_idx)
        passed, score, seconds = _predict_rows(model, table.loc[val_idx])
        fold_metrics.append(_metrics_for(table, val_idx, passed, score))
        oof.append(pd.DataFrame({"row": val_idx, "passed": passed, "score": score}))
        predict_times.append(seconds)
    final = _fit(name, cfg, table, dev_index)
    test_passed, test_score, seconds = _predict_rows(final, table.loc[test_index])
    predict_times.append(seconds)
    return {
        "folds": pd.DataFrame(fold_metrics),
        "oof": pd.concat(oof).set_index("row").sort_index(),
        "test": _metrics_for(table, test_index, test_passed, test_score),
        "predict_s": float(np.mean(predict_times)),
    }


def old_label_comparison(table: pd.DataFrame, config: dict) -> dict:
    """comp1-A scored against the OLD per-condition labels, on this same data."""
    agreement = (table["degraded_prediction"] == table["clean_prediction"]).groupby(table["condition"]).mean()
    old_reliable = table["condition"].map(agreement >= config["benchmark"]["old_label_agreement"])
    passed, score, _ = _predict_rows(get_gate_model("comp1-A", _eval_config(config)), table)
    return gate_metrics(old_reliable, passed, score, table["c2_correct"])


def previous_run_metrics(config: dict) -> dict | None:
    """The old per-condition validation result (e.g. 59.4% accuracy), if its file exists."""
    path = resolve_path(config, "results") / config["benchmark"]["previous_metrics_file"]
    if not path.is_file():
        return None
    old = json.loads(path.read_text(encoding="utf-8"))
    (tp, fn), (fp, tn) = old["confusion_matrix"]   # rows = truth [unreliable, reliable], cols = predicted
    return {**_count_metrics(tp, fn, fp, tn), "n_evaluations": old["n_evaluations"]}


# --- Selection ---------------------------------------------------------------------------------

def select_model(summary: dict[str, dict], config: dict) -> tuple[str, list[str]]:
    """Apply the config selection rule to {model: mean metrics}. Returns (winner, trace)."""
    bench = config["benchmark"]
    tol = bench["selection_tolerance"]
    candidates = [m for m, s in summary.items() if s["false_reject_rate"] <= bench["max_false_reject_rate"]]
    trace = [f"eligible (false_reject_rate <= {bench['max_false_reject_rate']}): {candidates}"]
    if not candidates:
        candidates = list(summary)
        trace.append(f"no model eligible; considering all: {candidates}")
    for criterion in bench["selection_order"]:
        values = {m: (INPUT_COST_TIER[m] if criterion == "speed" else summary[m][criterion]) for m in candidates}
        finite = {m: v for m, v in values.items() if not np.isnan(v)}
        if not finite:
            continue
        lower = criterion in LOWER_IS_BETTER
        best = min(finite.values()) if lower else max(finite.values())
        margin = 0 if criterion == "speed" else tol
        candidates = [m for m, v in finite.items() if abs(v - best) <= margin]
        trace.append(f"{criterion}: best {best:.4f}, within {margin} -> {candidates}")
        if len(candidates) == 1:
            break
    winner = min(candidates, key=COMPLEXITY.__getitem__)
    if len(candidates) > 1:
        trace.append(f"tie -> simpler model: {winner}")
    return winner, trace


def rank_models(summary: dict[str, dict], config: dict) -> list[str]:
    """Full ranking by applying the selection rule repeatedly."""
    remaining, ranking = dict(summary), []
    while remaining:
        winner, _ = select_model(remaining, config)
        ranking.append(winner)
        remaining.pop(winner)
    return ranking


def write_gate_model_to_config(name: str, config_path: str | Path) -> None:
    """Set `gate_model:` in the YAML file, keeping its comment and every other line."""
    path = Path(config_path)
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text, count = re.subn(r"^(gate_model:\s*)\S+", lambda m: m.group(1) + name, raw.replace("\r\n", "\n"),
                          count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"no `gate_model:` line in {path}")
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


# --- Outputs -------------------------------------------------------------------------------------

def _benchmark_table(results: dict, extra_rows: list[dict]) -> pd.DataFrame:
    rows = []
    for name, res in results.items():
        row = {"model": name, "label_source": LABEL_PER_CLIP, "n_folds": len(res["folds"])}
        for metric in METRICS:
            row[f"{metric}_mean"] = res["folds"][metric].mean()
            row[f"{metric}_std"] = res["folds"][metric].std(ddof=0)
            row[f"test_{metric}"] = res["test"][metric]
        rows.append(row)
    return pd.DataFrame(rows + extra_rows)


def plot_accuracy_vs_snr(results: dict, table: pd.DataFrame, out_path: Path) -> None:
    """Out-of-fold gate accuracy per injected-noise level, one line per model."""
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [label for _, label in SNR_CONDITIONS]
    for name, res in results.items():
        oof = res["oof"].join(table[["condition", "reliable"]])
        acc = [((oof["passed"] == oof["reliable"])[oof["condition"] == cond]).mean() for cond, _ in SNR_CONDITIONS]
        ax.plot(labels, acc, marker="o", label=name)
    ax.set_xlabel("Injected noise (SNR, dB)")
    ax.set_ylabel("Gate accuracy (cross-validated)")
    ax.set_ylim(0, 1.05)
    ax.set_title("Quality-gate accuracy vs noise level")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=100, metadata={"Software": None})
    plt.close(fig)


def measure_input_cost(config: dict) -> dict[str, float]:
    """Seconds to compute each model's inputs for one synthetic 5 s, 16 kHz clip."""
    sr = config["sample_rate"]
    t = np.arange(5 * sr) / sr
    y = (0.3 * np.sin(2 * np.pi * 150 * t)).astype(np.float32)

    def clock(fn) -> float:
        start = time.perf_counter()
        fn()
        return time.perf_counter() - start

    quality = clock(lambda: compute_quality(y, sr))
    mfcc = clock(lambda: mfcc_means(y, sr, config["n_mfcc"]))
    return {"comp1-A": quality, "comp1-B-logreg": quality + mfcc, "comp1-B-svm": quality + mfcc,
            "comp1-B-rf": quality + mfcc}


# --- Main entry ----------------------------------------------------------------------------------

def run_benchmark(config: dict, model_names: list[str] | None = None, select: bool = True,
                  save_outputs: bool = True, write_back: bool = True,
                  config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict | None:
    """Run the whole benchmark. Returns a summary dict, or None if gate_labels.csv is missing."""
    table = load_labels(config)
    if table is None:
        return None
    names = list(model_names or config["benchmark"]["models"])
    dev_index, test_index, folds = make_splits(table, config)
    print(f"{len(table)} rows, {table['participant_id'].nunique()} participants; "
          f"{len(folds)} folds; test set {len(test_index)} rows")

    results = {name: evaluate_model(name, table, dev_index, test_index, folds, config) for name in names}
    summary = {name: res["folds"][METRICS].mean().to_dict() for name, res in results.items()}

    old_same_data = old_label_comparison(table, config)
    previous = previous_run_metrics(config)
    extra = [{"model": "comp1-A", "label_source": "per_condition (this data)",
              **{f"{m}_mean": v for m, v in old_same_data.items()}}]
    if previous:
        extra.append({"model": "comp1-A", "label_source": "per_condition (previous run)",
                      **{f"{m}_mean": previous[m] for m in METRICS if m in previous}})
    bench_df = _benchmark_table(results, extra)
    print("\n" + bench_df[["model", "label_source", "accuracy_mean", "f1_mean", "false_accept_rate_mean",
                           "false_reject_rate_mean", "downstream_accuracy_mean"]].to_string(index=False))

    out = {"benchmark": bench_df, "results": results, "summary": summary,
           "no_gate_downstream_accuracy": float(table["c2_correct"].mean())}

    if select and summary:
        winner, trace = select_model(summary, config)
        ranking = rank_models(summary, config)
        test = None
        if len(ranking) >= 2:
            first, second = ranking[:2]
            oof = results[first]["oof"].join(results[second]["oof"], lsuffix="_a", rsuffix="_b")
            truth = table.loc[oof.index, "reliable"]
            test = {"models": [first, second],
                    **mcnemar(oof["passed_a"] == truth, oof["passed_b"] == truth)}
        reason = (f"{winner} selected by rule {config['benchmark']['selection_order']} "
                  f"(tolerance {config['benchmark']['selection_tolerance']}): " + "; ".join(trace))
        out.update(selected=winner, trace=trace, ranking=ranking, mcnemar=test, reason=reason)
        print(f"\nSelected: {winner}\n  " + "\n  ".join(trace))
        if test:
            print(f"McNemar {test['models'][0]} vs {test['models'][1]}: p = {test['p_value']:.4g}")

    if save_outputs:
        results_dir = resolve_path(config, "results")
        results_dir.mkdir(parents=True, exist_ok=True)
        bench_df.to_csv(results_dir / BENCHMARK_CSV, index=False, float_format="%.6f")
        plot_accuracy_vs_snr(results, table, results_dir / SNR_PNG)
        cost = measure_input_cost(config)
        pd.DataFrame([{"model": n, "input_s_per_clip": cost[n], "predict_s_per_clip": results[n]["predict_s"],
                       "total_s_per_clip": cost[n] + results[n]["predict_s"]} for n in results]
                     ).to_csv(results_dir / TIMING_CSV, index=False, float_format="%.6f")
        if select and summary:
            selected = {
                "selected_gate_model": out["selected"], "reason": out["reason"], "ranking": out["ranking"],
                "selection_order": config["benchmark"]["selection_order"],
                "cv_mean_metrics": summary, "test_metrics_selected": results[out["selected"]]["test"],
                "mcnemar_top_two": out["mcnemar"],
                "comp1A_old_labels_same_data": old_same_data, "comp1A_previous_run": previous,
                "no_gate_downstream_accuracy": out["no_gate_downstream_accuracy"],
                "n_rows": int(len(table)),
                "n_participants": int(table["participant_id"].nunique()),
                "config_version": str(config["config_version"]),
            }
            text = json.dumps(json_safe(selected), indent=2, allow_nan=False)   # NaN -> null
            (results_dir / SELECTED_JSON).write_text(text + "\n", encoding="utf-8", newline="\n")
            for name in results:
                if name in TRAINABLE:   # final models on ALL labelled rows, so the pipeline can load them
                    model = get_gate_model(name, config).fit(table, table["label"], table["participant_id"])
                    save_gate_model(model, config)
            if write_back:
                write_gate_model_to_config(out["selected"], config_path)
                print(f"Wrote gate_model: {out['selected']} to {config_path}")
    return out


def main() -> None:
    run_benchmark(load_config())


if __name__ == "__main__":
    main()
