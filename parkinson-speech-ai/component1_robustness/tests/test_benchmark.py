"""Tests for benchmark.py on a synthetic label table (no dataset, no audio)."""

import json

import numpy as np
import pandas as pd
import pytest

from component1_robustness import benchmark
from component1_robustness.benchmark import (
    BENCHMARK_CSV, SELECTED_JSON, SNR_PNG, auc_reliable, gate_metrics, load_labels, make_splits,
    mcnemar, run_benchmark, select_model, write_gate_model_to_config,
)
from component1_robustness.conditions import CONDITIONS
from component1_robustness.config import DEFAULT_CONFIG_PATH, load_config
from component1_robustness.labels import LABELS_CSV_NAME

CONDITION_SNR = {"clean": 40, "noise_snr_10db": 14, "noise_snr_5db": 8, "noise_snr_0db": 3,
                 "noise_snr_-5db": -2, "reverb_mild_rt0.3": 12, "reverb_heavy_rt0.6": 7,
                 "compression_high": 35, "compression_medium": 25, "compression_low": 15,
                 "distance_quiet_-6db": 30, "distance_far_-12db": 25}


def fake_label_table(n_participants: int = 20, seed: int = 0) -> pd.DataFrame:
    """Same columns as labels.py output. Reliability depends on SNR, with 10% label noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_participants):
        group = "PD" if p % 2 else "HC"
        truth = int(group == "PD")
        for cond, _ in CONDITIONS:
            snr = CONDITION_SNR[cond] + rng.normal(0, 3)
            reliable = (snr > 9) != (rng.random() < 0.1)
            pred = truth if (reliable or rng.random() < 0.5) else 1 - truth
            rows.append({
                "filename": f"p{p:02d}.wav", "participant_id": f"p{p:02d}", "group": group, "condition": cond,
                "duration_s": 4.0, "level_dbfs": -20 + rng.normal(0, 2), "clipping_pct": 0.0,
                "voice_activity_pct": 90.0, "estimated_snr_db": snr, "method": "hnr",
                "speech_band_contrast_db": snr,   # comp1-A input since v1.5; tracks SNR here
                **{f"mfcc_mean_{i + 1}": rng.normal(0, 1) + 0.05 * snr for i in range(13)},
                "clean_prediction": truth, "degraded_prediction": pred,
                "label": "reliable" if reliable else "unreliable",
            })
    return pd.DataFrame(rows)


def _config(tmp_path, with_previous: bool = True) -> dict:
    cfg = load_config()
    results = tmp_path / "results"
    results.mkdir(parents=True, exist_ok=True)
    fake_label_table().to_csv(results / LABELS_CSV_NAME, index=False)
    if with_previous:
        (results / "quality_gate_validation_metrics.json").write_text(json.dumps({
            "accuracy": 0.5944444444444444, "precision_unreliable": 0.7285714285714285,
            "recall_unreliable": 0.4857142857142857, "confusion_matrix": [[102, 108], [38, 112]],
            "n_evaluations": 360}), encoding="utf-8")
    cfg["paths"] = dict(cfg["paths"], results=str(results), models=str(tmp_path / "models"))
    return cfg


# --- Hand-calculated metrics ------------------------------------------------------------

# 10 clips: 5 reliable then 5 unreliable.
RELIABLE = [True] * 5 + [False] * 5
PASSED = [True, True, True, False, False, True, False, False, False, False]
SCORE = [0.9, 0.8, 0.7, 0.4, 0.3, 0.6, 0.2, 0.1, 0.05, 0.0]
C2_CORRECT = [True, True, False, True, True, False, True, True, True, True]
# Positive = unreliable. TP (unreliable, failed) = 4; FN (unreliable, passed) = 1 (row 6);
# FP (reliable, failed) = 2 (rows 4, 5); TN (reliable, passed) = 3.
HAND = {
    "accuracy": 7 / 10,                 # (TP + TN) / 10
    "precision": 4 / 6,                 # TP / (TP + FP)
    "recall": 4 / 5,                    # TP / (TP + FN)
    "f1": 8 / 11,                       # 2TP / (2TP + FP + FN)
    "false_accept_rate": 1 / 5,         # FN / unreliable
    "false_reject_rate": 2 / 5,         # FP / reliable
    "roc_auc": 23 / 25,                 # reliable 0.4 and 0.3 lose to unreliable 0.6: 2 of 25 pairs
    "downstream_accuracy": 2 / 4,       # passed rows 1, 2, 3, 6 -> C2 correct on 1 and 2
    "pass_rate": 4 / 10,
}


@pytest.mark.parametrize("metric", HAND)
def test_metrics_equal_hand_calculation_exactly(metric):
    assert gate_metrics(RELIABLE, PASSED, SCORE, C2_CORRECT)[metric] == HAND[metric]


def test_auc_ties_count_half():
    assert auc_reliable(np.array([True, False]), np.array([0.5, 0.5])) == 0.5


def test_auc_single_class_is_nan():
    assert np.isnan(auc_reliable(np.array([True, True]), np.array([0.1, 0.9])))


def test_mcnemar_known_answer():
    a = [True] * 8 + [False] * 2 + [True] * 5     # 8 clips only A right, 2 only B right, 5 both
    b = [False] * 8 + [True] * 2 + [True] * 5
    result = mcnemar(a, b)
    assert (result["only_first_correct"], result["only_second_correct"]) == (8, 2)
    assert result["p_value"] == pytest.approx(0.109375)   # exact binomial, two-sided: 2 * 56/1024


def test_mcnemar_identical_models():
    assert mcnemar([True, False], [True, False])["p_value"] == 1.0


# --- Splits -----------------------------------------------------------------------------------

@pytest.fixture
def split_setup(tmp_path):
    cfg = _config(tmp_path)
    table = load_labels(cfg)
    return table, cfg, make_splits(table, cfg)


def test_no_participant_in_both_train_and_test(split_setup):
    table, _, (dev, test, folds) = split_setup
    pid = table["participant_id"]
    assert not set(pid[dev]) & set(pid[test])
    for train, val in folds:
        assert not set(pid[train]) & set(pid[val])
        assert not set(pid[val]) & set(pid[test])


def test_folds_cover_dev_exactly_once(split_setup):
    _, _, (dev, _, folds) = split_setup
    val_rows = np.concatenate([val for _, val in folds])
    assert sorted(val_rows) == sorted(dev)
    assert len(folds) == 5


def test_splits_are_reproducible(split_setup):
    table, cfg, (dev, test, folds) = split_setup
    dev2, test2, folds2 = make_splits(table, cfg)
    assert (dev == dev2).all() and (test == test2).all()
    assert all((a == c).all() and (b == d).all() for (a, b), (c, d) in zip(folds, folds2))


# --- Selection rule ------------------------------------------------------------------------------

def _summary(**models):
    keys = ["false_accept_rate", "downstream_accuracy", "f1", "false_reject_rate"]
    return {name: dict(zip(keys, values)) for name, values in models.items()}


def test_lowest_far_wins():
    s = _summary(**{"comp1-A": (0.30, 0.9, 0.8, 0.1), "comp1-B-rf": (0.10, 0.7, 0.6, 0.2)})
    assert select_model(s, load_config())[0] == "comp1-B-rf"


def test_far_tie_goes_to_downstream_accuracy():
    s = _summary(**{"comp1-A": (0.105, 0.70, 0.8, 0.1), "comp1-B-rf": (0.100, 0.85, 0.6, 0.2)})
    assert select_model(s, load_config())[0] == "comp1-B-rf"


def test_full_tie_goes_to_simpler_model():
    s = _summary(**{"comp1-B-rf": (0.1, 0.8, 0.7, 0.2), "comp1-B-logreg": (0.1, 0.8, 0.7, 0.2)})
    assert select_model(s, load_config())[0] == "comp1-B-logreg"


def test_reject_everything_gate_not_eligible():
    s = _summary(**{"comp1-A": (0.0, np.nan, 0.5, 1.0), "comp1-B-rf": (0.2, 0.8, 0.7, 0.2)})
    assert select_model(s, load_config())[0] == "comp1-B-rf"


def test_write_back_changes_only_gate_model_line(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_bytes(b"seed: 42\r\ngate_model: comp1-A           # keep this comment\r\nn_mfcc: 13\r\n")
    write_gate_model_to_config("comp1-B-rf", path)
    assert path.read_bytes() == b"seed: 42\r\ngate_model: comp1-B-rf           # keep this comment\r\nn_mfcc: 13\r\n"


# --- Full run -------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def full_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bench")
    cfg = _config(tmp)
    cfg_file = tmp / "component1.yaml"
    cfg_file.write_bytes(DEFAULT_CONFIG_PATH.read_bytes())   # a copy: the real config is never touched
    out = run_benchmark(cfg, config_path=cfg_file)
    return out, cfg, tmp, cfg_file


def test_outputs_written(full_run):
    _, cfg, tmp, _ = full_run
    for name in (BENCHMARK_CSV, SNR_PNG, SELECTED_JSON, benchmark.TIMING_CSV):
        assert (tmp / "results" / name).stat().st_size > 0


def test_csv_has_mean_std_and_test_columns(full_run):
    _, _, tmp, _ = full_run
    df = pd.read_csv(tmp / "results" / BENCHMARK_CSV)
    for metric in benchmark.METRICS:
        assert {f"{metric}_mean", f"{metric}_std", f"test_{metric}"} <= set(df.columns)
    per_clip = df[df["label_source"] == "per_clip"]
    assert set(per_clip["model"]) == set(load_config()["benchmark"]["models"])


def test_old_numbers_shown_next_to_new(full_run):
    _, _, tmp, _ = full_run
    df = pd.read_csv(tmp / "results" / BENCHMARK_CSV).set_index("label_source")
    assert df.loc["per_condition (previous run)", "accuracy_mean"] == pytest.approx(0.594444, abs=1e-6)
    assert df.loc["per_condition (previous run)", "false_accept_rate_mean"] == pytest.approx(108 / 210, abs=1e-6)
    assert "per_condition (this data)" in df.index


def test_selected_json_and_write_back(full_run):
    out, _, tmp, cfg_file = full_run
    selected = json.loads((tmp / "results" / SELECTED_JSON).read_text(encoding="utf-8"))
    assert selected["selected_gate_model"] == out["selected"]
    assert out["selected"] in selected["reason"]
    assert selected["mcnemar_top_two"]["models"] == out["ranking"][:2]
    assert f"gate_model: {out['selected']}" in cfg_file.read_text(encoding="utf-8")


def test_trainable_models_saved(full_run):
    _, _, tmp, _ = full_run
    saved = {p.name for p in (tmp / "models").iterdir()}
    assert "component1_gate_comp1-B-rf.joblib" in saved


def test_same_seed_identical_csv(tmp_path):
    cfg = _config(tmp_path)
    run_benchmark(cfg, select=False, write_back=False)
    first = (tmp_path / "results" / BENCHMARK_CSV).read_bytes()
    run_benchmark(cfg, select=False, write_back=False)
    assert (tmp_path / "results" / BENCHMARK_CSV).read_bytes() == first


def test_missing_labels_message(tmp_path, capsys):
    cfg = load_config()
    cfg["paths"] = dict(cfg["paths"], results=str(tmp_path / "empty"))
    assert run_benchmark(cfg) is None
    assert "Label table not found" in capsys.readouterr().out


