"""Known-answer tests for degradation.py, using synthetic signals only."""

import re
from pathlib import Path

import numpy as np
import pytest

from component1_robustness.degradation import (
    add_babble_noise,
    add_noise_from_file,
    add_pink_noise,
    add_synthetic_reverb,
    add_white_noise,
    apply_gain,
    simulate_compression,
)

SNR_TOL_DB = 0.01
PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)))


def _true_snr_db(clean: np.ndarray, noisy: np.ndarray) -> float:
    """SNR from the known clean part and the known added part (noisy - clean)."""
    added = noisy - clean
    return 20 * np.log10(_rms(clean) / _rms(added))


# --- SNR known answers -------------------------------------------------------

@pytest.mark.parametrize("snr_db", [0, 5, 10, 20])
def test_white_noise_exact_snr(tone, snr_db):
    noisy = add_white_noise(tone, snr_db, np.random.default_rng(42))
    assert _true_snr_db(tone, noisy) == pytest.approx(snr_db, abs=SNR_TOL_DB)


@pytest.mark.parametrize("snr_db", [0, 5, 10, 20])
def test_pink_noise_exact_snr(tone, snr_db):
    noisy = add_pink_noise(tone, snr_db, np.random.default_rng(42))
    assert _true_snr_db(tone, noisy) == pytest.approx(snr_db, abs=SNR_TOL_DB)


@pytest.mark.parametrize("snr_db", [0, 10])
def test_noise_from_file_exact_snr(tone, noise, snr_db):
    noisy = add_noise_from_file(tone, noise, snr_db, np.random.default_rng(42))
    assert _true_snr_db(tone, noisy) == pytest.approx(snr_db, abs=SNR_TOL_DB)


@pytest.mark.parametrize("snr_db", [0, 10])
def test_babble_noise_exact_snr(tone, make_tone, snr_db):
    babble = make_tone(freq_hz=220.0, duration_s=2.0)
    noisy = add_babble_noise(tone, babble, snr_db, np.random.default_rng(42))
    assert _true_snr_db(tone, noisy) == pytest.approx(snr_db, abs=SNR_TOL_DB)


# --- Gain known answer -------------------------------------------------------

@pytest.mark.parametrize("gain_db", [-6, -12, 3])
def test_apply_gain_exact_rms_change(tone, gain_db):
    out = apply_gain(tone, gain_db)
    change_db = 20 * np.log10(_rms(out) / _rms(tone))
    assert change_db == pytest.approx(gain_db, abs=0.01)


# --- Reproducibility ---------------------------------------------------------

RANDOM_FUNCS = {
    "white": lambda y, n, sr, rng: add_white_noise(y, 10, rng),
    "pink": lambda y, n, sr, rng: add_pink_noise(y, 10, rng),
    "reverb": lambda y, n, sr, rng: add_synthetic_reverb(y, sr, 0.3, rng),
    "babble": lambda y, n, sr, rng: add_babble_noise(y, n, 10, rng),
    "from_file": lambda y, n, sr, rng: add_noise_from_file(y, n, 10, rng),
}


@pytest.fixture
def long_noise(make_noise) -> np.ndarray:
    """Noise longer than the 5 s tone, so cropping uses the rng."""
    return make_noise(duration_s=8.0)


@pytest.mark.parametrize("name", RANDOM_FUNCS)
def test_same_seed_identical_output(tone, long_noise, sr, name):
    f = RANDOM_FUNCS[name]
    a = f(tone, long_noise, sr, np.random.default_rng(123))
    b = f(tone, long_noise, sr, np.random.default_rng(123))
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("name", RANDOM_FUNCS)
def test_different_seed_different_output(tone, long_noise, sr, name):
    f = RANDOM_FUNCS[name]
    a = f(tone, long_noise, sr, np.random.default_rng(1))
    b = f(tone, long_noise, sr, np.random.default_rng(2))
    assert not np.array_equal(a, b)


@pytest.mark.parametrize("call", [
    lambda y: add_white_noise(y, 10),
    lambda y: add_pink_noise(y, 10),
    lambda y: add_synthetic_reverb(y, 16000, 0.3),
    lambda y: add_noise_from_file(y, y, 10),
    lambda y: add_babble_noise(y, y, 10),
])
def test_rng_is_required(tone, call):
    with pytest.raises(TypeError):
        call(tone)


def test_no_unseeded_default_rng_in_component1():
    pattern = re.compile(r"default_rng\(\s*\)")
    offenders = [p.name for p in PACKAGE_DIR.glob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


# --- Length preserved --------------------------------------------------------

LENGTH_CASES = {
    "white": lambda y, sr, rng, mk: add_white_noise(y, 5, rng),
    "pink": lambda y, sr, rng, mk: add_pink_noise(y, 5, rng),
    "babble_short_source": lambda y, sr, rng, mk: add_babble_noise(y, mk(duration_s=1.0), 5, rng),
    "babble_long_source": lambda y, sr, rng, mk: add_babble_noise(y, mk(duration_s=9.0), 5, rng),
    "from_file_short": lambda y, sr, rng, mk: add_noise_from_file(y, mk(duration_s=1.3), 5, rng),
    "from_file_long": lambda y, sr, rng, mk: add_noise_from_file(y, mk(duration_s=9.0), 5, rng),
    "from_file_equal": lambda y, sr, rng, mk: add_noise_from_file(y, mk(duration_s=5.0), 5, rng),
    "reverb_0.3": lambda y, sr, rng, mk: add_synthetic_reverb(y, sr, 0.3, rng),
    "reverb_0.6": lambda y, sr, rng, mk: add_synthetic_reverb(y, sr, 0.6, rng),
    "compression_high": lambda y, sr, rng, mk: simulate_compression(y, sr, "high"),
    "compression_medium": lambda y, sr, rng, mk: simulate_compression(y, sr, "medium"),
    "compression_low": lambda y, sr, rng, mk: simulate_compression(y, sr, "low"),
    "gain": lambda y, sr, rng, mk: apply_gain(y, -6),
}


@pytest.mark.parametrize("name", LENGTH_CASES)
def test_output_length_equals_input(tone, sr, make_noise, name):
    out = LENGTH_CASES[name](tone, sr, np.random.default_rng(0), make_noise)
    assert len(out) == len(tone)


# --- add_noise_from_file specifics ------------------------------------------

def test_noise_from_file_long_noise_uses_a_contiguous_segment(tone, long_noise):
    """The added part is the seeded random slice of the noise, scaled to the SNR."""
    n = len(tone)
    start = int(np.random.default_rng(7).integers(0, len(long_noise) - n + 1))  # same draw as the function
    segment = long_noise[start:start + n]
    added = add_noise_from_file(tone, long_noise, 10, np.random.default_rng(7)) - tone
    expected = segment * (_rms(added) / _rms(segment))
    np.testing.assert_allclose(added, expected, rtol=1e-9, atol=1e-12)


def test_noise_from_file_empty_noise_raises(tone):
    with pytest.raises(ValueError):
        add_noise_from_file(tone, np.array([]), 10, np.random.default_rng(0))


def test_compression_is_deterministic(tone, sr):
    np.testing.assert_array_equal(simulate_compression(tone, sr, "low"), simulate_compression(tone, sr, "low"))
