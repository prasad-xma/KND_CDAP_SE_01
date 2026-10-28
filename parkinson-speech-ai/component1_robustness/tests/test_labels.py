"""Tests for labels.py. No real dataset: fake features/predictions and a tiny synthetic folder."""

import math

import joblib
import numpy as np
import pandas as pd
import pytest
import soundfile as sf
from sklearn.dummy import DummyClassifier

from component1_robustness import labels
from component1_robustness.conditions import CONDITIONS
from component1_robustness.config import load_config
from component1_robustness.features_check import NO_PREDICTION
from component1_robustness.labels import (
    RELIABLE, UNRELIABLE, build_label_table, find_clips, label_clip,
    participant_id_from_path,
)
from component1_robustness.quality_metrics import compute_quality
from component2_phonation.features import FEATURE_NAMES

from conftest import make_vowel

TOL = {"jitter": 0.20, "shimmer": 0.20, "hnr": 0.15, "mean_f0": 0.05}
CLEAN = {"jitter": 0.010, "shimmer": 0.050, "hnr": 20.0, "mean_f0": 150.0}
METRIC_COLUMNS = list(compute_quality(np.ones(8000) * 0.1, 8000))


# --- label_clip ----------------------------------------------------------------

def test_same_features_same_prediction_is_reliable():
    assert label_clip(CLEAN, dict(CLEAN), 1, 1, TOL) == RELIABLE


@pytest.mark.parametrize("clean_pred,degraded_pred", [(1, 0), (0, 1)])
def test_prediction_flip_is_unreliable(clean_pred, degraded_pred):
    assert label_clip(CLEAN, dict(CLEAN), clean_pred, degraded_pred, TOL) == UNRELIABLE


@pytest.mark.parametrize("feature", list(TOL))
def test_one_feature_beyond_tolerance_is_unreliable(feature):
    moved = dict(CLEAN, **{feature: CLEAN[feature] * (1 + TOL[feature] + 0.01)})
    assert label_clip(CLEAN, moved, 0, 0, TOL) == UNRELIABLE


@pytest.mark.parametrize("feature", list(TOL))
def test_one_feature_just_inside_tolerance_is_reliable(feature):
    moved = dict(CLEAN, **{feature: CLEAN[feature] * (1 + TOL[feature] - 0.01)})
    assert label_clip(CLEAN, moved, 0, 0, TOL) == RELIABLE


def test_no_voiced_frames_after_degradation_is_unreliable():
    assert label_clip(CLEAN, None, 1, NO_PREDICTION, TOL) == UNRELIABLE


def test_nan_feature_is_unreliable():
    assert label_clip(CLEAN, dict(CLEAN, hnr=math.nan), 1, 1, TOL) == UNRELIABLE


def test_participant_id_is_file_stem(tmp_path):
    assert participant_id_from_path(tmp_path / "AH_064F_7AB034C9.wav") == "AH_064F_7AB034C9"


# --- build_label_table on a tiny synthetic dataset ----------------------------

SR = 8000  # the real AH dataset is 8 kHz
SYNTHETIC_CLIPS = {"PD_AH": [("pd_a", 140.0), ("pd_b", 180.0)], "HC_AH": [("hc_a", 120.0), ("hc_b", 210.0)]}


def _make_dataset(root):
    raw = root / "raw"
    for folder, clips in SYNTHETIC_CLIPS.items():
        (raw / folder).mkdir(parents=True)
        for name, f0 in clips:
            sf.write(raw / folder / f"{name}.wav", make_vowel(f0_hz=f0, duration_s=3.0, sr=SR), SR)
    model = DummyClassifier(strategy="constant", constant=1).fit(np.zeros((2, len(FEATURE_NAMES))), [0, 1])
    joblib.dump({"model": model, "feature_names": FEATURE_NAMES}, root / "model.joblib")
    return raw


def _config_for(root, raw) -> dict:
    """Test config pointing at the synthetic folder."""
    cfg = load_config()
    cfg["paths"] = dict(cfg["paths"], raw_data=str(raw), results=str(root / "results"),
                        component2_model=str(root / "model.joblib"))
    return cfg


def test_table_has_mfcc_columns(built):
    _, table, _ = built
    assert sum(c.startswith("mfcc_mean_") for c in table.columns) == load_config()["n_mfcc"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("labels")
    cfg = _config_for(root, _make_dataset(root))
    return cfg, build_label_table(cfg), root


def test_one_row_per_clip_and_condition(built):
    _, table, _ = built
    n_clips = sum(len(v) for v in SYNTHETIC_CLIPS.values())
    assert len(table) == n_clips * len(CONDITIONS)
    assert not table.duplicated(["filename", "condition"]).any()
    assert set(table["condition"]) == {name for name, _ in CONDITIONS}


def test_no_missing_values(built):
    _, table, _ = built
    assert not table.isna().any().any()


def test_required_columns(built):
    _, table, _ = built
    required = ["filename", "participant_id", "condition", *METRIC_COLUMNS, "label"]
    assert all(col in table.columns for col in required)
    assert set(table["label"]) <= {RELIABLE, UNRELIABLE}


def test_csv_written_to_results(built):
    cfg, table, root = built
    saved = pd.read_csv(root / "results" / labels.LABELS_CSV_NAME)
    assert len(saved) == len(table)
    assert list(saved.columns) == list(table.columns)


def test_clean_condition_is_reliable(built):
    _, table, _ = built
    assert (table.loc[table["condition"] == "clean", "label"] == RELIABLE).all()


def test_groups_from_folders(built):
    _, table, _ = built
    groups = table.drop_duplicates("filename").set_index("filename")["group"]
    assert groups["pd_a.wav"] == "PD" and groups["hc_a.wav"] == "HC"


def test_same_config_same_table(tmp_path, monkeypatch):
    """Seeded: building twice from the same config gives an identical table."""
    monkeypatch.setattr(labels, "CONDITIONS", [c for c in CONDITIONS if c[0] in {"clean", "noise_snr_5db", "reverb_heavy_rt0.6"}])
    cfg = _config_for(tmp_path, _make_dataset(tmp_path))
    first = build_label_table(cfg)
    second = build_label_table(cfg)
    pd.testing.assert_frame_equal(first, second)


def test_missing_dataset_prints_message_and_returns_none(tmp_path, capsys):
    cfg = _config_for(tmp_path, tmp_path / "does_not_exist")
    assert build_label_table(cfg) is None
    assert "Dataset not found" in capsys.readouterr().out
    assert not (tmp_path / "results").exists()


def test_empty_dataset_folder_also_handled(tmp_path, capsys):
    (tmp_path / "raw" / "PD_AH").mkdir(parents=True)
    assert build_label_table(_config_for(tmp_path, tmp_path / "raw")) is None
    assert "Dataset not found" in capsys.readouterr().out


def test_find_clips_sorted_with_groups(tmp_path):
    raw = _make_dataset(tmp_path)
    found = [(p.name, g) for p, g in find_clips(raw)]
    assert found == [("pd_a.wav", "PD"), ("pd_b.wav", "PD"), ("hc_a.wav", "HC"), ("hc_b.wav", "HC")]


def test_main_runs_without_dataset(monkeypatch, tmp_path, capsys):
    cfg = _config_for(tmp_path, tmp_path / "missing")
    monkeypatch.setattr(labels, "load_config", lambda: cfg)
    labels.main()   # must not raise
    assert "Dataset not found" in capsys.readouterr().out
