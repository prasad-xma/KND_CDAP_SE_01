"""Sanity tests for every available gate model, on synthetic audio only."""

import numpy as np
import pandas as pd
import pytest

from component1_robustness.config import load_config
from component1_robustness.gate_models import (
    FAIL, GATE_NAMES, PASS, TRAINABLE, Comp1A_RuleBased, gate_inputs, get_gate_model, load_gate_model,
    save_gate_model,
)

from conftest import make_vowel

SR = 16000
CONFIG = load_config()
AVAILABLE = list(GATE_NAMES)
TRAINABLE_AVAILABLE = list(TRAINABLE)


def _noisy(y: np.ndarray, snr_db: float, seed: int) -> np.ndarray:
    noise = np.random.default_rng(seed).standard_normal(len(y))
    return y + noise * np.sqrt(np.mean(y ** 2)) / np.sqrt(np.mean(noise ** 2)) / 10 ** (snr_db / 20)


def _wobbly_vowel(f0: float, seed: int, duration_s: float = 5.0) -> np.ndarray:
    """Vowel with a slow random loudness wobble, so clips differ like real voices."""
    rng = np.random.default_rng(seed)
    y = make_vowel(f0_hz=f0, duration_s=duration_s)
    t = np.arange(len(y)) / SR
    return y * (1 + 0.1 * np.sin(2 * np.pi * rng.uniform(2, 6) * t))


# --- Synthetic training set and trained models (built once) -----------------------

@pytest.fixture(scope="module")
def training_set() -> tuple[pd.DataFrame, list[str]]:
    rows, labels = [], []
    for i, f0 in enumerate([100, 120, 140, 170, 200, 230]):
        clean = _wobbly_vowel(f0, seed=i)
        for y, label in [(clean, "reliable"), (_noisy(clean, 30, 100 + i), "reliable"),
                         (_noisy(clean, 25, 200 + i), "reliable"),
                         (_noisy(clean, 0, 300 + i), "unreliable"), (_noisy(clean, -5, 400 + i), "unreliable"),
                         (0.1 * np.random.default_rng(500 + i).standard_normal(len(clean)), "unreliable")]:
            rows.append(gate_inputs(y, SR, CONFIG))
            labels.append(label)
    return pd.DataFrame(rows), labels


@pytest.fixture(scope="module")
def trained(training_set) -> dict:
    X, y = training_set
    models = {}
    for name in AVAILABLE:
        model = get_gate_model(name, CONFIG)
        models[name] = model.fit(X, y)
    return models


def _inputs(y):
    return gate_inputs(y, SR, CONFIG)


# --- Sanity checks on every available model ---------------------------------------

@pytest.mark.parametrize("name", AVAILABLE)
def test_clean_vowel_passes(name, trained):
    result = trained[name].predict(_inputs(_wobbly_vowel(155, seed=99)))
    assert result["decision"] == PASS and result["reason"] == "ok"


@pytest.mark.parametrize("name", AVAILABLE)
def test_white_noise_only_fails(name, trained):
    noise = 0.1 * np.random.default_rng(999).standard_normal(SR * 5)
    assert trained[name].predict(_inputs(noise))["decision"] == FAIL


@pytest.mark.parametrize("name", AVAILABLE)
def test_silence_fails(name, trained):
    result = trained[name].predict(_inputs(np.zeros(SR * 5)))
    assert result == {"decision": FAIL, "quality_score": 0.0, "reason": "no_voice"}


@pytest.mark.parametrize("name", AVAILABLE)
@pytest.mark.parametrize("seconds,reason", [(2.9, "too_short"), (15.1, "too_long")])
def test_duration_rule(name, seconds, reason, trained):
    result = trained[name].predict(_inputs(make_vowel(duration_s=seconds)))
    assert result == {"decision": FAIL, "quality_score": 0.0, "reason": reason}


@pytest.mark.parametrize("name", AVAILABLE)
@pytest.mark.parametrize("seconds", [3.0, 15.0])
def test_duration_limits_inclusive(name, seconds, trained):
    assert trained[name].predict(_inputs(_wobbly_vowel(155, 98, seconds)))["reason"] not in {"too_short", "too_long"}


@pytest.mark.parametrize("name", AVAILABLE)
def test_clipped_clip_fails(name, trained):
    clipped = np.clip(4.0 * make_vowel(), -1.0, 1.0)   # peak 2.0 before clipping
    result = trained[name].predict(_inputs(clipped))
    assert result == {"decision": FAIL, "quality_score": 0.0, "reason": "clipped"}


@pytest.mark.parametrize("name", AVAILABLE)
def test_output_format(name, trained):
    result = trained[name].predict(_inputs(_noisy(_wobbly_vowel(155, 97), 10, 7)))
    assert set(result) == {"decision", "quality_score", "reason"}
    assert result["decision"] in {PASS, FAIL}
    assert 0.0 <= result["quality_score"] <= 100.0
    assert isinstance(result["reason"], str)


@pytest.mark.parametrize("name", TRAINABLE_AVAILABLE)
def test_same_seed_identical_predictions(name, training_set):
    X, y = training_set
    a, b = get_gate_model(name, CONFIG).fit(X, y), get_gate_model(name, CONFIG).fit(X, y)
    probes = [_inputs(_noisy(_wobbly_vowel(160, 90 + k), snr, k)) for k, snr in enumerate([20, 10, 3])]
    assert [a.predict(q) for q in probes] == [b.predict(q) for q in probes]


@pytest.mark.parametrize("name", TRAINABLE_AVAILABLE)
def test_predict_before_fit_raises(name):
    with pytest.raises(RuntimeError):
        get_gate_model(name, CONFIG).predict(_inputs(_wobbly_vowel(155, 99)))


# --- comp1-A specifics -------------------------------------------------------------

def test_comp1a_score_never_rises_with_more_noise():
    gate = Comp1A_RuleBased(CONFIG)
    clean = _wobbly_vowel(150, seed=5)
    scores = [gate.predict(gate_inputs(_noisy(clean, snr, 42), SR, CONFIG))["quality_score"]
              for snr in [30, 25, 20, 15, 10, 5, 0]]
    assert all(later <= earlier + 1e-9 for earlier, later in zip(scores, scores[1:])), scores


@pytest.mark.parametrize("estimate,expected", [(10.0, 50.0), (30.0, 100.0), (-10.0, 0.0), (20.0, 75.0),
                                               (60.0, 100.0), (-np.inf, 0.0)])
def test_comp1a_score_linear_map(estimate, expected):
    assert Comp1A_RuleBased(CONFIG).score(estimate) == pytest.approx(expected)


def test_comp1a_low_snr_reason():
    q = gate_inputs(_noisy(_wobbly_vowel(150, 6), 0, 1), SR, CONFIG)
    assert Comp1A_RuleBased(CONFIG).predict(q)["reason"] == "low_snr"


# --- Factory, availability, save / load ----------------------------------------------

def test_unknown_name_raises():
    with pytest.raises(ValueError):
        get_gate_model("comp1-Z", CONFIG)


def test_config_default_gate_is_known():
    assert CONFIG["gate_model"] in GATE_NAMES


def test_gate_inputs_has_mfcc_means():
    q = gate_inputs(make_vowel(), SR, CONFIG)
    assert sum(k.startswith("mfcc_mean_") for k in q) == CONFIG["n_mfcc"]


def test_gate_inputs_resamples_for_mfcc():
    """An 8 kHz and a 16 kHz copy of the same vowel get similar MFCC means."""
    import librosa
    y16 = make_vowel()
    y8 = librosa.resample(y16, orig_sr=SR, target_sr=8000)
    a, b = gate_inputs(y16, SR, CONFIG), gate_inputs(y8, 8000, CONFIG)
    assert a["mfcc_mean_2"] == pytest.approx(b["mfcc_mean_2"], rel=0.2)


@pytest.mark.parametrize("name", TRAINABLE_AVAILABLE)
def test_save_and_load_roundtrip(name, trained, tmp_path):
    cfg = dict(CONFIG, paths=dict(CONFIG["paths"], models=str(tmp_path)))
    path = save_gate_model(trained[name], cfg)
    assert path.name == f"component1_gate_{name}.joblib"
    loaded = load_gate_model(name, cfg)
    q = _inputs(_noisy(_wobbly_vowel(165, 80), 12, 8))
    assert loaded.predict(q) == trained[name].predict(q)


def test_comp1a_cannot_be_saved(tmp_path):
    cfg = dict(CONFIG, paths=dict(CONFIG["paths"], models=str(tmp_path)))
    with pytest.raises(ValueError):
        save_gate_model(Comp1A_RuleBased(cfg), cfg)
    assert isinstance(load_gate_model("comp1-A", cfg), Comp1A_RuleBased)
