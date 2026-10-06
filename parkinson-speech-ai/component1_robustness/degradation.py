"""Synthetic audio degradation for Component 1 (acoustic robustness testing).

No external noise/RIR corpora are bundled here — degradations are generated
programmatically so the experiment needs no extra downloads. This is a
reasonable phase-1 proxy, not a substitute for real recorded noise/RIRs:
    - "noise" is synthesized (white / pink / babble-via-mixing), not real
      recorded traffic/fan/crowd audio.
    - "reverb" is convolution with a synthetic exponential-decay impulse
      response, not a measured room impulse response (RIR).
    - "compression" is simulated via low-pass filtering + bit-depth
      quantization, not a real codec (no ffmpeg/lame available in this
      environment) — it approximates the perceptual effect (reduced
      bandwidth + reduced dynamic range) without being bit-exact to MP3/AAC.
Swap in real noise/RIR/codec sources later if this proxy proves too easy.
"""

import numpy as np
from scipy.signal import butter, lfilter


def _rms(y):
    return np.sqrt(np.mean(y ** 2) + 1e-12)


def add_white_noise(y, snr_db, rng=None):
    rng = rng or np.random.default_rng()
    noise = rng.standard_normal(len(y))
    signal_rms = _rms(y)
    noise_rms = _rms(noise)
    target_noise_rms = signal_rms / (10 ** (snr_db / 20))
    noise = noise * (target_noise_rms / (noise_rms + 1e-12))
    return y + noise


def add_pink_noise(y, snr_db, rng=None):
    """Pink (1/f) noise — a rough proxy for steady background hum/fan noise."""
    rng = rng or np.random.default_rng()
    white = rng.standard_normal(len(y))
    # Simple 1/f shaping via cumulative-sum trick (Voss-McCartney-ish approximation).
    pink = np.cumsum(white)
    pink = pink - np.mean(pink)
    pink = pink / (_rms(pink) + 1e-12)
    signal_rms = _rms(y)
    target_noise_rms = signal_rms / (10 ** (snr_db / 20))
    return y + pink * target_noise_rms


def add_babble_noise(y, babble_source, snr_db):
    """Mix in another speech recording at a fixed SNR as a babble-noise proxy."""
    if len(babble_source) < len(y):
        reps = int(np.ceil(len(y) / len(babble_source)))
        babble_source = np.tile(babble_source, reps)
    babble = babble_source[: len(y)]
    signal_rms = _rms(y)
    babble_rms = _rms(babble)
    target_rms = signal_rms / (10 ** (snr_db / 20))
    babble = babble * (target_rms / (babble_rms + 1e-12))
    return y + babble


def add_synthetic_reverb(y, sr, rt60_sec=0.3, rng=None):
    """Convolve with a synthetic exponential-decay impulse response.

    Not a measured RIR — a decaying noise burst is a common cheap
    approximation of the general effect of reverberation (energy smearing
    over time) without simulating actual room geometry.
    """
    rng = rng or np.random.default_rng()
    ir_len = int(sr * rt60_sec)
    decay = np.exp(-np.linspace(0, 6, ir_len))  # ~60dB decay over rt60_sec
    ir = rng.standard_normal(ir_len) * decay
    ir = ir / (np.sqrt(np.sum(ir ** 2)) + 1e-12)
    wet = np.convolve(y, ir, mode="full")[: len(y)]
    dry_rms = _rms(y)
    wet_rms = _rms(wet)
    wet = wet * (dry_rms / (wet_rms + 1e-12))
    return 0.6 * y + 0.4 * wet


def simulate_compression(y, sr, level="medium"):
    """Approximate lossy compression via bandwidth reduction + requantization.

    level: "high" (mild), "medium", "low" (heavy) quality.
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
    quantized = np.round(filtered * (levels / 2)) / (levels / 2)
    return quantized


def apply_gain(y, gain_db):
    """Simulate a quieter/further-away recording via a gain change."""
    return y * (10 ** (gain_db / 20))
