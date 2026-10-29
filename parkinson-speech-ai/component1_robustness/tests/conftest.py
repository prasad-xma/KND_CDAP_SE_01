"""Shared pytest setup for Component 1: import path + synthetic audio fixtures.

Tests never touch the real datasets; every signal here is generated.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

REPO_ROOT = Path(__file__).resolve().parents[2]  # parkinson-speech-ai/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from component1_robustness.config import load_config  # noqa: E402  (needs REPO_ROOT on sys.path)

TEST_SEED = 42
TEST_SR = 16000
TEST_DURATION_S = 5.0


@pytest.fixture
def sr() -> int:
    """Sample rate used by all synthetic fixtures."""
    return TEST_SR


@pytest.fixture
def make_tone():
    """Factory: pure sine tone of given frequency, duration and amplitude."""

    def _make(freq_hz: float = 150.0, duration_s: float = TEST_DURATION_S,
              amplitude: float = 0.5, sr: int = TEST_SR) -> np.ndarray:
        t = np.arange(int(duration_s * sr)) / sr
        return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float64)

    return _make


@pytest.fixture
def tone(make_tone) -> np.ndarray:
    """Default 150 Hz, 5 s, 0.5-amplitude tone (vowel-like F0)."""
    return make_tone()


def make_vowel(f0_hz: float = 150.0, duration_s: float = TEST_DURATION_S,
               n_harmonics: int = 5, peak: float = 0.5, sr: int = TEST_SR) -> np.ndarray:
    """Vowel-like harmonic tone: F0 plus harmonics with 1/k amplitudes, peak-normalised."""
    t = np.arange(int(duration_s * sr)) / sr
    y = sum((1.0 / k) * np.sin(2 * np.pi * f0_hz * k * t) for k in range(1, n_harmonics + 1))
    return peak * y / np.max(np.abs(y))


# A real app take is quiet before the person starts speaking and after they stop.
# comp1-A (config v1.5) and the voice check measure exactly that start/stop contrast,
# so a perfectly steady synthetic tone with no start looks like room hum. Clips that
# must PASS are shaped like a real take.
TAKE_LEAD_S = 0.5
TAKE_TAIL_S = 0.3


def as_take(y: np.ndarray, sr: int = TEST_SR, lead_s: float = TAKE_LEAD_S, tail_s: float = TAKE_TAIL_S,
            floor: float = 1e-4, seed: int = TEST_SEED) -> np.ndarray:
    """Same length as y, but silent for the first lead_s and last tail_s (10 ms fades),
    over a faint seeded noise floor (about -80 dBFS), like a tap-to-record take."""
    y = np.asarray(y, dtype=np.float64)
    n = len(y)
    env = np.ones(n)
    n_lead, n_tail, ramp = int(lead_s * sr), int(tail_s * sr), int(0.01 * sr)
    env[:n_lead] = 0.0
    env[n - n_tail:] = 0.0
    env[n_lead:n_lead + ramp] = np.linspace(0.0, 1.0, ramp)
    env[n - n_tail - ramp:n - n_tail] = np.linspace(1.0, 0.0, ramp)
    return y * env + floor * np.random.default_rng(seed).standard_normal(n)


def clean_take(duration_s: float = TEST_DURATION_S, sr: int = TEST_SR) -> np.ndarray:
    """A clean "aaaa" take that the gate should PASS: synthetic vowel plus a faint
    hiss (about -60 dBFS), shaped like a tap-to-record take."""
    hiss = 1e-3 * np.random.default_rng(0).standard_normal(int(duration_s * sr))
    return as_take(make_vowel(duration_s=duration_s, sr=sr) + hiss, sr=sr)


@pytest.fixture
def vowel() -> np.ndarray:
    """Default 150 Hz harmonic 'vowel', 5 s, peak 0.5."""
    return make_vowel()


def make_ddk(rate_hz: float = 5.0, burst_s: float = 0.13, duration_s: float = TEST_DURATION_S,
             floor_db: float = -45.0, sr: int = TEST_SR, seed: int = TEST_SEED) -> np.ndarray:
    """'pa-ta-ka'-like clip: short vowel bursts at rate_hz with gaps, over a low noise floor.

    Each burst has 10 ms fade-in/out. floor_db sets the background noise relative
    to the speech RMS (real recordings never have digitally silent gaps).
    """
    t = np.arange(int(duration_s * sr)) / sr
    on = ((t % (1.0 / rate_hz)) < burst_s).astype(float)
    ramp = int(0.01 * sr)
    envelope = np.convolve(on, np.ones(ramp) / ramp, mode="same")
    y = make_vowel(duration_s=duration_s, sr=sr) * envelope
    floor = np.random.default_rng(seed).standard_normal(len(y))
    return y + floor * np.sqrt(np.mean(y ** 2)) * 10 ** (floor_db / 20)


# --- Shared test helpers --------------------------------------------------------------

def rms(x: np.ndarray) -> float:
    """Root-mean-square level, computed here independently of the code under test."""
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))


def true_snr_db(clean: np.ndarray, x: np.ndarray) -> float:
    """SNR of x against its known clean part: clean energy / (x - clean) energy, in dB."""
    clean = np.asarray(clean, dtype=np.float64)
    return float(10 * np.log10(np.sum(clean ** 2) / np.sum((np.asarray(x, dtype=np.float64) - clean) ** 2)))


def write_wav(tmp_path, name: str, y: np.ndarray, sr: int = TEST_SR) -> str:
    """Write y as a WAV file in tmp_path and return its path."""
    path = tmp_path / name
    sf.write(path, y, sr)
    return str(path)


def gate_config(tmp_path, **overrides) -> dict:
    """The real Component 1 config with outputs written under tmp_path, plus any overrides."""
    cfg = load_config()
    cfg["paths"] = dict(cfg["paths"], outputs=str(tmp_path / "outputs"))
    cfg.update(overrides)
    return cfg
