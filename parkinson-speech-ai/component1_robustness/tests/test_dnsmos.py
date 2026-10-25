"""Tests for the optional DNSMOS wrapper."""

import sys

import numpy as np
import pytest

from component1_robustness import dnsmos
from component1_robustness.config import load_config, resolve_path

from conftest import make_vowel

MODEL = resolve_path(load_config(), "dnsmos_model")
needs_dnsmos = pytest.mark.skipif(not dnsmos.is_available(MODEL), reason="onnxruntime or DNSMOS model missing")


def test_unavailable_when_onnxruntime_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", None)   # makes `import onnxruntime` fail
    assert dnsmos.is_available(MODEL) is False


def test_unavailable_when_model_file_missing(tmp_path):
    assert dnsmos.is_available(tmp_path / "missing.onnx") is False


@pytest.fixture(scope="module")
def scorer():
    return dnsmos.DnsmosScorer(MODEL) if dnsmos.is_available(MODEL) else None


@needs_dnsmos
def test_scores_in_mos_range(scorer):
    scores = scorer(make_vowel(), 16000)
    assert set(scores) == set(dnsmos.SCORE_KEYS)
    assert all(0.5 <= v <= 5.5 for v in scores.values())


@needs_dnsmos
def test_same_input_same_scores(scorer):
    y = make_vowel()
    assert scorer(y, 16000) == scorer(y, 16000)


@needs_dnsmos
def test_noise_lowers_background_score(scorer):
    clean = make_vowel()
    noisy = clean + np.random.default_rng(0).standard_normal(len(clean)) * np.sqrt(np.mean(clean ** 2))  # 0 dB
    assert scorer(noisy, 16000)["dnsmos_bak"] < scorer(clean, 16000)["dnsmos_bak"] - 0.5


@needs_dnsmos
def test_noise_only_scores_lowest(scorer):
    noise = 0.1 * np.random.default_rng(1).standard_normal(16000 * 5)
    assert scorer(noise, 16000)["dnsmos_ovrl"] < scorer(make_vowel(), 16000)["dnsmos_ovrl"]


@needs_dnsmos
@pytest.mark.parametrize("seconds,sr", [(1.0, 16000), (3.0, 8000), (12.0, 16000)])
def test_short_long_and_8khz_clips_work(scorer, seconds, sr):
    scores = scorer(make_vowel(duration_s=seconds, sr=sr), sr)
    assert all(np.isfinite(v) for v in scores.values())


@needs_dnsmos
def test_empty_input_does_not_crash(scorer):
    assert all(np.isfinite(v) for v in scorer(np.array([]), 16000).values())
