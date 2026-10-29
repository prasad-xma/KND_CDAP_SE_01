"""Shared pytest setup for Component 2: import path + synthetic audio fixtures.

Tests never touch the real datasets; every signal here is generated.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]  # parkinson-speech-ai/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEST_SEED = 42
TEST_SR = 16000
TEST_DURATION_S = 3.0
TEST_F0_HZ = 150.0


def make_vowel(f0_hz: float = TEST_F0_HZ, duration_s: float = TEST_DURATION_S,
               n_harmonics: int = 5, peak: float = 0.5, sr: int = TEST_SR) -> np.ndarray:
    """Vowel-like harmonic tone: F0 plus harmonics with 1/k amplitudes, peak-normalised."""
    t = np.arange(int(duration_s * sr)) / sr
    y = sum((1.0 / k) * np.sin(2 * np.pi * f0_hz * k * t) for k in range(1, n_harmonics + 1))
    return peak * y / np.max(np.abs(y))


def make_silence(duration_s: float = TEST_DURATION_S, sr: int = TEST_SR) -> np.ndarray:
    """Digital silence - no voiced frames should be detected in this."""
    return np.zeros(int(duration_s * sr), dtype=np.float64)


@pytest.fixture
def sr() -> int:
    return TEST_SR


@pytest.fixture
def vowel() -> np.ndarray:
    """Default 150 Hz harmonic 'vowel', 3 s, peak 0.5."""
    return make_vowel()


@pytest.fixture
def silence() -> np.ndarray:
    """3 s of digital silence."""
    return make_silence()
