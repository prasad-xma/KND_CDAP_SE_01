"""Synthetic audio degradation for Component 1 (acoustic robustness testing).

No external noise/RIR corpora are bundled here — degradations are generated
programmatically so the experiment needs no extra downloads. This is a
reasonable phase-1 proxy, not a substitute for real recorded noise/RIRs:
    - "noise" is synthesized white noise, not real
      recorded traffic/fan/crowd audio.
    - "reverb" is convolution with a synthetic exponential-decay impulse
      response, not a measured room impulse response (RIR).
    - "compression" is simulated via low-pass filtering + bit-depth
      quantization, not a real codec — it approximates the perceptual effect
      (reduced bandwidth + reduced dynamic range) without being bit-exact to
      MP3/AAC.

Reproducibility: every function that uses randomness takes a REQUIRED
np.random.Generator. Callers create it from the config seed, so the same
seed always gives the same degraded audio.

Length: every function returns an array the same length as its input.
"""

import numpy as np
from scipy.signal import butter, lfilter

EPS = 1e-12


def _rms(y: np.ndarray) -> float:
    """Root-mean-square level of a signal."""
    return float(np.sqrt(np.mean(y ** 2) + EPS))


def _scale_to_snr(y: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Scale noise so that rms(y) / rms(noise) equals snr_db (in dB)."""
    target_noise_rms = _rms(y) / (10 ** (snr_db / 20))
    return noise * (target_noise_rms / _rms(noise))


def add_white_noise(y: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """Add Gaussian white noise at the given SNR (dB)."""
    noise = rng.standard_normal(len(y))
    return y + _scale_to_snr(y, noise, snr_db)


def add_synthetic_reverb(y: np.ndarray, sr: int, rt60_sec: float,
                         rng: np.random.Generator) -> np.ndarray:
    """Convolve with a synthetic exponential-decay impulse response.

    Not a measured RIR — a decaying noise burst is a common cheap
    approximation of reverberation (energy smeared over time).
    """
    ir_len = int(sr * rt60_sec)
    decay = np.exp(-np.linspace(0, 6, ir_len))  # ~60 dB decay over rt60_sec
    ir = rng.standard_normal(ir_len) * decay
    ir = ir / (np.sqrt(np.sum(ir ** 2)) + EPS)
    wet = np.convolve(y, ir, mode="full")[: len(y)]  # trim the tail: same length as input
    wet = wet * (_rms(y) / _rms(wet))
    return 0.6 * y + 0.4 * wet


def simulate_compression(y: np.ndarray, sr: int, level: str = "medium") -> np.ndarray:
    """Approximate lossy compression via bandwidth reduction + requantization.

    level: "high" (mild), "medium", "low" (heavy) quality. Deterministic.
    """
    cutoff_hz, bits = {
        "high": (7000, 12),
        "medium": (4000, 8),
        "low": (2000, 6),
    }[level]

    nyquist = sr / 2
    normalized_cutoff = min(cutoff_hz / nyquist, 0.99)
    b, a = butter(4, normalized_cutoff, btype="low")
    filtered = lfilter(b, a, y)

    levels = 2 ** bits
    return np.round(filtered * (levels / 2)) / (levels / 2)


def apply_gain(y: np.ndarray, gain_db: float) -> np.ndarray:
    """Simulate a quieter/further-away recording via a gain change. Deterministic."""
    return y * (10 ** (gain_db / 20))
