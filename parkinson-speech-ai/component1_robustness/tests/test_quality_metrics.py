"""Known-answer tests for quality_metrics.py, using synthetic signals only."""

import numpy as np
import pytest

from component1_robustness.config import load_config
from component1_robustness.quality_metrics import (
    check_duration,
    clipping_pct,
    compute_quality,
    duration_s,
    estimate_quality_db,
    has_usable_silence,
    hnr,
    mean_level_dbfs,
    silence_based_snr,
    voice_activity_pct,
)

SR = 16000
SNR_SWEEP_DB = [30, 25, 20, 15, 10, 5, 0]


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)))


def _gated_tone(sr: int = SR, duration: float = 5.0, on_s: float = 0.5, off_s: float = 0.5,
                freq: float = 150.0, amp: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Tone switched on/off (like syllables with pauses). Returns (signal, on_mask)."""
    t = np.arange(int(duration * sr)) / sr
    on = (t % (on_s + off_s)) < on_s
    return amp * np.sin(2 * np.pi * freq * t) * on, on


def _add_noise_at_snr(clean: np.ndarray, active: np.ndarray, snr_db: float, seed: int = 42) -> np.ndarray:
    """Add white noise so that (RMS of clean where active) / (noise RMS) = snr_db.

    The same seed gives the same noise shape, only its level changes with snr_db.
    """
    noise = np.random.default_rng(seed).standard_normal(len(clean))
    noise = noise / _rms(noise)
    signal_rms = _rms(clean[active])
    return clean + noise * signal_rms / (10 ** (snr_db / 20))


# --- Duration ----------------------------------------------------------------

@pytest.mark.parametrize("seconds,expected", [
    (2.9, (False, "too_short")),
    (3.0, (True, "ok")),
    (15.0, (True, "ok")),
    (15.1, (False, "too_long")),
])
def test_check_duration_boundaries(seconds, expected):
    cfg = load_config()
    y = np.zeros(int(round(seconds * SR)))
    assert check_duration(y, SR, cfg["min_duration_s"], cfg["max_duration_s"]) == expected


def test_duration_s_known_answer():
    assert duration_s(np.zeros(SR * 4), SR) == pytest.approx(4.0)


# --- Clipping ----------------------------------------------------------------

def test_clipping_pct_five_percent(tone):
    y = tone.copy()                                   # amplitude 0.5, so no clipping yet
    rng = np.random.default_rng(0)
    idx = rng.choice(len(y), size=int(0.05 * len(y)), replace=False)
    y[idx] = rng.choice([-1.0, 1.0], size=len(idx))
    assert clipping_pct(y) == pytest.approx(5.0, abs=0.5)


def test_clipping_pct_clean_tone_is_zero(tone):
    assert clipping_pct(tone) == 0.0


def test_clipping_pct_empty_is_zero():
    assert clipping_pct(np.array([])) == 0.0


# --- Voice activity ----------------------------------------------------------

def test_voice_activity_digital_silence_is_zero():
    assert voice_activity_pct(np.zeros(SR * 5), SR) == pytest.approx(0.0, abs=1.0)


def test_voice_activity_near_silence_is_zero():
    hiss = 1e-5 * np.random.default_rng(0).standard_normal(SR * 5)  # about -100 dBFS
    assert voice_activity_pct(hiss, SR) == pytest.approx(0.0, abs=1.0)


def test_voice_activity_continuous_tone_is_hundred(tone):
    assert voice_activity_pct(tone, SR) == pytest.approx(100.0, abs=1.0)


def test_voice_activity_half_on_is_about_fifty():
    """2 s on / 2 s off: about 50%, plus a little because frames overlap each edge."""
    y, _ = _gated_tone(duration=12.0, on_s=2.0, off_s=2.0)
    assert voice_activity_pct(y, SR) == pytest.approx(50.0, abs=5.0)


# --- Level -------------------------------------------------------------------

def test_mean_level_dbfs_full_scale_sine():
    t = np.arange(SR) / SR
    y = np.sin(2 * np.pi * 100 * t)                   # RMS = 1/sqrt(2) = -3.01 dBFS
    assert mean_level_dbfs(y) == pytest.approx(-3.01, abs=0.01)


# --- Silence-based SNR -------------------------------------------------------

@pytest.mark.parametrize("snr_db", [10, 15, 20, 25])
def test_silence_based_snr_known_answer(snr_db):
    clean, on = _gated_tone()
    noisy = _add_noise_at_snr(clean, on, snr_db)
    assert silence_based_snr(noisy) == pytest.approx(snr_db, abs=2.0)


def test_has_usable_silence():
    gated, _ = _gated_tone()
    continuous = 0.5 * np.sin(2 * np.pi * 150 * np.arange(SR * 5) / SR)
    assert has_usable_silence(gated, SR) is True
    assert has_usable_silence(continuous, SR) is False


def test_hnr_requires_sr(tone):
    with pytest.raises(TypeError):
        hnr(tone)


# --- Monotonic: more noise never raises the estimate ------------------------

def _sweep(make_signal, measure) -> list[float]:
    return [measure(make_signal(snr)) for snr in SNR_SWEEP_DB]


def _assert_non_increasing(values: list[float]):
    for louder_noise, prev in zip(values[1:], values[:-1]):
        assert louder_noise <= prev + 1e-9, f"estimate rose: {values}"


def test_monotonic_silence_based_snr():
    clean, on = _gated_tone()
    _assert_non_increasing(_sweep(lambda s: _add_noise_at_snr(clean, on, s), silence_based_snr))


def test_monotonic_hnr_on_continuous_tone(tone):
    on = np.ones(len(tone), bool)
    _assert_non_increasing(_sweep(lambda s: _add_noise_at_snr(tone, on, s), lambda y: hnr(y, SR)))


@pytest.mark.parametrize("signal", ["gated", "continuous"])
def test_monotonic_estimate_quality_db(signal, tone):
    clean, on = _gated_tone() if signal == "gated" else (tone, np.ones(len(tone), bool))
    values = _sweep(lambda s: _add_noise_at_snr(clean, on, s), lambda y: estimate_quality_db(y, SR)[0])
    _assert_non_increasing(values)


# --- compute_quality ---------------------------------------------------------

def test_compute_quality_keys_and_values(tone):
    q = compute_quality(tone, SR)
    assert set(q) == {"duration_s", "level_dbfs", "clipping_pct", "voice_activity_pct",
                      "estimated_snr_db", "method"}
    assert q["duration_s"] == pytest.approx(5.0)
    assert q["clipping_pct"] == 0.0
    assert q["voice_activity_pct"] == pytest.approx(100.0, abs=1.0)
    assert q["method"] in {"silence_snr", "hnr"}
