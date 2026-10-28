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

Threshold tuning (config benchmark.tune_threshold, v1.6). Priority: GOOD RECORDINGS MUST PASS.
    For each model, the pass threshold on its 0-1 score (P(reliable) for comp1-B, the
    contrast score for comp1-A) is set from the pooled out-of-fold scores of the
    development set: the HIGHEST threshold whose false_reject_rate <= target_false_reject_rate.
    Highest, because among thresholds that meet the false-reject target it lets through
    the fewest unreliable clips. Fold and test metrics are then computed at that threshold.
    Hard-rule failures (clipping, no voice, duration) stay FAIL whatever the threshold.
    The held-out test set never influences the threshold, so its numbers stay honest.

Selection (config benchmark.selection_order), lexicographic with a tolerance:
    eligible: false_reject_rate <= target_false_reject_rate when tuning (pooled out-of-fold),
              otherwise <= max_false_reject_rate (a gate rejecting everything has FAR 0)
    then lowest FAR -> highest downstream accuracy -> highest F1 -> fastest (input-cost tier)
    any remaining tie -> the simpler model.
    So with tuning on, the question is: "at <= 10% good recordings rejected, which gate
    lets the fewest bad recordings through?"

Write-back: gate_model, plus the tuned threshold of the winner (gate_pass_probability
for comp1-B, comp1a_pass_db for comp1-A). Targets met / not met are reported in
selected_gate_model.json ("targets").

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
from component1_robustness.voice_check import OVERRIDABLE_REASONS  # noqa: E402
from component1_robustness.features_check import NO_PREDICTION  # noqa: E402
from component1_robustness.labels import LABELS_CSV_NAME, RELIABLE  # noqa: E402
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


def _predict_rows(model, rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    """(passed, score 0-1, mean seconds per prediction, hard_fail) for every row.

    hard_fail: the row failed a hard rule (duration, clipping, no voice), not the model's
    own judgement, so no threshold can make it pass.
    """
    passed, score, hard_fail = [], [], []
    start = time.perf_counter()
    for quality in rows.to_dict(orient="records"):
        result = model.predict(quality)
        passed.append(result["decision"] == PASS)
        score.append(result["quality_score"] / 100.0)
        hard_fail.append(result["reason"] not in OVERRIDABLE_REASONS)
    seconds = (time.perf_counter() - start) / max(len(rows), 1)
    return np.array(passed), np.array(score), seconds, np.array(hard_fail)


# --- Threshold tuning ---------------------------------------------------------------------

def tuning_enabled(config: dict) -> bool:
    bench = config["benchmark"]
    return bool(bench.get("tune_threshold")) and bench.get("target_false_reject_rate") is not None


def pass_at(score, hard_fail, threshold: float) -> np.ndarray:
    """PASS = no hard-rule failure AND score >= threshold."""
    return ~np.asarray(hard_fail, bool) & (np.asarray(score, float) >= threshold)


def tune_threshold(score, reliable, hard_fail, target_frr: float) -> float:
    """Highest threshold whose false_reject_rate <= target_frr (fewest false accepts at that FRR).

    Candidates are the scores of reliable clips. If even the lowest one misses the target
    (hard-rule failures alone exceed it), the lowest is returned: everything the hard rules
    allow then passes.
    """
    score, reliable = np.asarray(score, float), np.asarray(reliable, bool)
    hard_fail = np.asarray(hard_fail, bool)
    candidates = np.unique(score[reliable & ~hard_fail])
    if len(candidates) == 0 or reliable.sum() == 0:
        return 0.0
    for threshold in candidates[::-1]:                       # highest first
        frr = (~pass_at(score[reliable], hard_fail[reliable], threshold)).mean()
        if frr <= target_frr:
            return float(threshold)
    return float(candidates[0])


def threshold_to_config(name: str, threshold: float, config: dict) -> tuple[str, float]:
    """(config key, value) that makes the live gate use this 0-1 score threshold.

    comp1-B: gate_pass_probability = threshold.
    comp1-A: the score is 50 + 50 * (contrast - pass_db) / span, so the matching
             comp1a_pass_db = pass_db + span * (100 * threshold - 50) / 50.
    Rounded DOWN (4 decimals), so a clip exactly at the threshold still passes.
    """
    if name == "comp1-A":
        pass_db = float(config.get("comp1a_pass_db", 10.0))
        span = float(config["comp1a_score_span_db"])
        value = pass_db + span * (100.0 * threshold - 50.0) / 50.0
        return "comp1a_pass_db", float(np.floor(value * 1e4) / 1e4)
    return "gate_pass_probability", float(np.floor(threshold * 1e4) / 1e4)


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
    fold_preds, predict_times = [], []
    for train_idx, val_idx in folds:
        model = _fit(name, cfg, table, train_idx)
        passed, score, seconds, hard_fail = _predict_rows(model, table.loc[val_idx])
        fold_preds.append(pd.DataFrame({"row": val_idx, "passed": passed, "score": score,
                                        "hard_fail": hard_fail}))
        predict_times.append(seconds)
    oof = pd.concat(fold_preds).set_index("row").sort_index()

    # Threshold from the development set's out-of-fold scores only (never the test set).
    threshold = None
    if tuning_enabled(config):
        threshold = tune_threshold(oof["score"], table.loc[oof.index, "reliable"], oof["hard_fail"],
                                   config["benchmark"]["target_false_reject_rate"])
        for frame in fold_preds + [oof]:
            frame["passed"] = pass_at(frame["score"], frame["hard_fail"], threshold)

    fold_metrics = [_metrics_for(table, f["row"].to_numpy(), f["passed"].to_numpy(), f["score"].to_numpy())
                    for f in fold_preds]
    final = _fit(name, cfg, table, dev_index)
    test_passed, test_score, seconds, test_hard = _predict_rows(final, table.loc[test_index])
    if threshold is not None:
        test_passed = pass_at(test_score, test_hard, threshold)
    predict_times.append(seconds)
    return {
        "folds": pd.DataFrame(fold_metrics),
        "oof": oof[["passed", "score"]],
        "oof_metrics": _metrics_for(table, oof.index, oof["passed"].to_numpy(), oof["score"].to_numpy()),
        "threshold": threshold,
        "test": _metrics_for(table, test_index, test_passed, test_score),
        "predict_s": float(np.mean(predict_times)),
    }


def old_label_comparison(table: pd.DataFrame, config: dict) -> dict:
    """comp1-A scored against the OLD per-condition labels, on this same data."""
    agreement = (table["degraded_prediction"] == table["clean_prediction"]).groupby(table["condition"]).mean()
    old_reliable = table["condition"].map(agreement >= config["benchmark"]["old_label_agreement"])
    passed, score, _, _ = _predict_rows(get_gate_model("comp1-A", _eval_config(config)), table)
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

def select_model(summary: dict[str, dict], config: dict, max_frr: float | None = None) -> tuple[str, list[str]]:
    """Apply the config selection rule to {model: mean metrics}. Returns (winner, trace).

    max_frr overrides benchmark.max_false_reject_rate (used with threshold tuning).
    """
    bench = config["benchmark"]
    tol = bench["selection_tolerance"]
    limit = bench["max_false_reject_rate"] if max_frr is None else max_frr
    candidates = [m for m, s in summary.items() if s["false_reject_rate"] <= limit]
    trace = [f"eligible (false_reject_rate <= {limit}): {candidates}"]
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


def rank_models(summary: dict[str, dict], config: dict, max_frr: float | None = None) -> list[str]:
    """Full ranking by applying the selection rule repeatedly."""
    remaining, ranking = dict(summary), []
    while remaining:
        winner, _ = select_model(remaining, config, max_frr)
        ranking.append(winner)
        remaining.pop(winner)
    return ranking


def write_config_value(key: str, value, config_path: str | Path) -> None:
    """Set a top-level `key:` in the YAML file, keeping its comment and every other line."""
    path = Path(config_path)
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text, count = re.subn(rf"^({re.escape(key)}:\s*)\S+", lambda m: m.group(1) + str(value),
                          raw.replace("\r\n", "\n"), count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"no `{key}:` line in {path}")
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def write_gate_model_to_config(name: str, config_path: str | Path) -> None:
    """Set `gate_model:` in the YAML file, keeping its comment and every other line."""
    write_config_value("gate_model", name, config_path)


def target_report(metrics: dict, config: dict) -> dict:
    """Did these metrics meet the stated targets? (None where a target is not set.)"""
    bench = config["benchmark"]
    frr_target, far_target = bench.get("target_false_reject_rate"), bench.get("target_false_accept_rate")
    return {
        "target_false_reject_rate": frr_target,
        "target_false_accept_rate": far_target,
        "false_reject_rate": metrics["false_reject_rate"],
        "false_accept_rate": metrics["false_accept_rate"],
        "false_reject_target_met": None if frr_target is None else bool(metrics["false_reject_rate"] <= frr_target),
        "false_accept_target_met": None if far_target is None else bool(metrics["false_accept_rate"] <= far_target),
    }


# --- Outputs -------------------------------------------------------------------------------------

def _benchmark_table(results: dict, extra_rows: list[dict]) -> pd.DataFrame:
    rows = []
    for name, res in results.items():
        row = {"model": name, "label_source": LABEL_PER_CLIP, "n_folds": len(res["folds"]),
               "threshold": res.get("threshold")}
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

    # With tuning, eligibility is judged on the pooled out-of-fold FRR the threshold was tuned to.
    tuned = tuning_enabled(config)
    max_frr = config["benchmark"]["target_false_reject_rate"] if tuned else None
    selection_summary = ({n: dict(s, false_reject_rate=results[n]["oof_metrics"]["false_reject_rate"])
                          for n, s in summary.items()} if tuned else summary)

    if select and summary:
        winner, trace = select_model(selection_summary, config, max_frr)
        ranking = rank_models(selection_summary, config, max_frr)
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
        out["targets"] = {"cross_validation": target_report(summary[winner], config),
                          "test": target_report(results[winner]["test"], config)}
        if tuned:
            print(f"Tuned threshold ({winner}): {results[winner]['threshold']:.4f} "
                  f"for false_reject_rate <= {max_frr}")
        for where, rep in out["targets"].items():
            if rep["target_false_reject_rate"] is not None:
                print(f"Targets ({where}): good rejected {rep['false_reject_rate']:.1%} "
                      f"(target <= {rep['target_false_reject_rate']:.0%}, met: {rep['false_reject_target_met']}); "
                      f"bad let through {rep['false_accept_rate']:.1%} "
                      f"(target <= {rep['target_false_accept_rate']:.0%}, met: {rep['false_accept_target_met']})"
                      if rep["target_false_accept_rate"] is not None else
                      f"Targets ({where}): good rejected {rep['false_reject_rate']:.1%} "
                      f"(target <= {rep['target_false_reject_rate']:.0%}, met: {rep['false_reject_target_met']})")

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
                "threshold_tuning": {
                    "enabled": tuned,
                    "thresholds": {n: results[n]["threshold"] for n in results},
                    "pooled_oof_metrics": {n: results[n]["oof_metrics"] for n in results},
                },
                "targets": out["targets"],
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
                if tuned:
                    key, value = threshold_to_config(out["selected"], results[out["selected"]]["threshold"], config)
                    write_config_value(key, value, config_path)
                    print(f"Wrote {key}: {value} to {config_path}")
    return out


def main() -> None:
    run_benchmark(load_config())


if __name__ == "__main__":
    main()
