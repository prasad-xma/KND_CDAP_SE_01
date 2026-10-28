"""Known-answer tests for degradation.py, using synthetic signals only."""

import re
from pathlib import Path

import numpy as np
import pytest

from component1_robustness.degradation import (
    add_synthetic_reverb,
    add_white_noise,
    apply_gain,
    simulate_compression,
)

from conftest import rms, true_snr_db

SNR_TOL_DB = 0.01
PACKAGE_DIR = Path(__file__).resolve().parents[1]


# --- SNR known answers -------------------------------------------------------

@pytest.mark.parametrize("snr_db", [0, 5, 10, 20])
def test_white_noise_exact_snr(tone, snr_db):
    noisy = add_white_noise(tone, snr_db, np.random.default_rng(42))
    assert true_snr_db(tone, noisy) == pytest.approx(snr_db, abs=SNR_TOL_DB)


# --- Gain known answer -------------------------------------------------------

@pytest.mark.parametrize("gain_db", [-6, -12, 3])
def test_apply_gain_exact_rms_change(tone, gain_db):
    out = apply_gain(tone, gain_db)
    change_db = 20 * np.log10(rms(out) / rms(tone))
    assert change_db == pytest.approx(gain_db, abs=0.01)


# --- Reproducibility ---------------------------------------------------------

RANDOM_FUNCS = {
    "white": lambda y, sr, rng: add_white_noise(y, 10, rng),
    "reverb": lambda y, sr, rng: add_synthetic_reverb(y, sr, 0.3, rng),
}


@pytest.mark.parametrize("name", RANDOM_FUNCS)
def test_same_seed_identical_output(tone, sr, name):
    f = RANDOM_FUNCS[name]
    a = f(tone, sr, np.random.default_rng(123))
    b = f(tone, sr, np.random.default_rng(123))
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("name", RANDOM_FUNCS)
def test_different_seed_different_output(tone, sr, name):
    f = RANDOM_FUNCS[name]
    a = f(tone, sr, np.random.default_rng(1))
    b = f(tone, sr, np.random.default_rng(2))
    assert not np.array_equal(a, b)


@pytest.mark.parametrize("call", [
    lambda y: add_white_noise(y, 10),
    lambda y: add_synthetic_reverb(y, 16000, 0.3),
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
    "white": lambda y, sr, rng: add_white_noise(y, 5, rng),
    "reverb_0.3": lambda y, sr, rng: add_synthetic_reverb(y, sr, 0.3, rng),
    "reverb_0.6": lambda y, sr, rng: add_synthetic_reverb(y, sr, 0.6, rng),
    "compression_high": lambda y, sr, rng: simulate_compression(y, sr, "high"),
    "compression_medium": lambda y, sr, rng: simulate_compression(y, sr, "medium"),
    "compression_low": lambda y, sr, rng: simulate_compression(y, sr, "low"),
    "gain": lambda y, sr, rng: apply_gain(y, -6),
}


@pytest.mark.parametrize("name", LENGTH_CASES)
def test_output_length_equals_input(tone, sr, name):
    out = LENGTH_CASES[name](tone, sr, np.random.default_rng(0))
    assert len(out) == len(tone)


def test_compression_is_deterministic(tone, sr):
    np.testing.assert_array_equal(simulate_compression(tone, sr, "low"), simulate_compression(tone, sr, "low"))
