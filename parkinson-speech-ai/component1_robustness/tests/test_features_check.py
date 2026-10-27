"""Tests for features_check.py: Component 2 features on arrays + preservation check."""

import math
import os
import tempfile

import numpy as np
import pytest

from component1_robustness import features_check
from component1_robustness.config import load_config
from component1_robustness.enhancement import enhance
from component1_robustness.features_check import compare_features, phonation_features, relative_diff
from component2_phonation.features import FEATURE_NAMES

from conftest import make_vowel

SR = 16000
TOLERANCES = load_config()["feature_tolerances"]


@pytest.fixture(scope="module")
def vowel_features() -> dict:
    """Component 2 features of the clean 150 Hz vowel (computed once: pYIN is slow)."""
    return phonation_features(make_vowel(), SR)


# --- phonation_features --------------------------------------------------------

def test_returns_component2_feature_names(vowel_features):
    assert list(vowel_features) == FEATURE_NAMES


def test_mean_f0_known_answer(vowel_features):
    assert vowel_features["mean_f0"] == pytest.approx(150.0, abs=1.5)


def test_silence_has_no_features():
    assert phonation_features(np.zeros(SR * 3), SR) is None


def test_temp_wav_is_deleted(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    phonation_features(make_vowel(duration_s=3.0), SR)
    assert os.listdir(tmp_path) == []


def test_uses_component2_extractor_not_a_copy(monkeypatch):
    calls = []
    monkeypatch.setattr(features_check, "extract_phonation_features",
                        lambda path: calls.append(path) or {"mean_f0": 1.0})
    assert phonation_features(make_vowel(duration_s=3.0), SR) == {"mean_f0": 1.0}
    assert len(calls) == 1 and calls[0].endswith(".wav")


# --- "none" enhancement preserves everything -----------------------------------

def test_none_gives_identical_features_and_preserved(vowel_features):
    after = phonation_features(enhance(make_vowel(), SR, "none", seed=42), SR)
    assert after == vowel_features
    result = compare_features(vowel_features, after, TOLERANCES)
    assert result["preserved"] is True
    assert all(d == 0.0 for d in result["per_feature"].values())
    assert set(result["per_feature"]) == set(TOLERANCES)


# --- Shift beyond tolerance -> not preserved ----------------------------------

def test_real_pitch_shift_beyond_tolerance_not_preserved(vowel_features):
    """150 -> 165 Hz is a 10% F0 change; mean_f0 tolerance is 5%."""
    shifted = phonation_features(make_vowel(f0_hz=165.0), SR)
    result = compare_features(vowel_features, shifted, TOLERANCES)
    assert result["per_feature"]["mean_f0"] == pytest.approx(0.10, abs=0.01)
    assert result["preserved"] is False


BEFORE = {"jitter": 0.010, "shimmer": 0.050, "hnr": 20.0, "mean_f0": 150.0}
TOL = {"jitter": 0.20, "shimmer": 0.20, "hnr": 0.15, "mean_f0": 0.05}


@pytest.mark.parametrize("feature,factor,expected", [
    ("jitter", 1.19, True),     # 19% < 20%
    ("jitter", 1.21, False),    # 21% > 20%
    ("hnr", 0.86, True),        # 14% < 15%
    ("hnr", 0.84, False),       # 16% > 15%
    ("mean_f0", 1.04, True),    # 4% < 5%
    ("mean_f0", 0.94, False),   # 6% > 5%
])
def test_single_feature_shift(feature, factor, expected):
    after = dict(BEFORE, **{feature: BEFORE[feature] * factor})
    result = compare_features(BEFORE, after, TOL)
    assert result["preserved"] is expected
    assert result["per_feature"][feature] == pytest.approx(abs(factor - 1))


def test_nan_feature_not_preserved():
    assert compare_features(BEFORE, dict(BEFORE, shimmer=math.nan), TOL)["preserved"] is False


def test_missing_feature_not_preserved():
    after = {k: v for k, v in BEFORE.items() if k != "hnr"}
    assert compare_features(BEFORE, after, TOL)["preserved"] is False


@pytest.mark.parametrize("before,after", [(None, BEFORE), (BEFORE, None), (None, None)])
def test_no_voiced_frames_not_preserved(before, after):
    assert compare_features(before, after, TOL) == {"per_feature": {}, "preserved": False}


def test_only_features_with_tolerances_are_checked():
    after = dict(BEFORE, mean_rms=999.0)   # not in TOL, so ignored
    assert compare_features(dict(BEFORE, mean_rms=0.1), after, TOL)["preserved"] is True


@pytest.mark.parametrize("before,after,expected", [
    (100.0, 110.0, 0.10),
    (100.0, 90.0, 0.10),
    (-20.0, -22.0, 0.10),   # HNR can be negative: uses |before|
    (0.0, 0.0, 0.0),
])
def test_relative_diff_known_answers(before, after, expected):
    assert relative_diff(before, after) == pytest.approx(expected)


def test_relative_diff_nan():
    assert math.isnan(relative_diff(math.nan, 1.0))


def test_ddk_features_are_component3_features():
    """DDK recordings are checked with Component 3's own extractor and feature names."""
    from component3_ddk.features import FEATURE_NAMES as DDK_FEATURE_NAMES
    from conftest import make_ddk
    feats = features_check.ddk_features(make_ddk(), SR)
    assert feats is not None and list(feats) == DDK_FEATURE_NAMES
