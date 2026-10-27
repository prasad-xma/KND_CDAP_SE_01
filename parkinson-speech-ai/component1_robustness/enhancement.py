"""Real audio enhancement/cleanup — the piece the proposal calls "Stage 4:
Enhancement / Cleanup Algorithms" (slide 17).

enhance(y, sr, method, seed, noise_ref=None) works on in-memory arrays. Methods:
  - "noisereduce_nonstationary": spectral gating that adapts to noise that
    changes over the recording (phone background noise is rarely constant).
  - "noisereduce_stationary": spectral gating with one fixed noise profile,
    taken from `noise_ref` (a noise-only stretch of audio) when given.
  - "wiener": classic Wiener filter (scipy.signal.wiener) in the time domain.
  - "none": no enhancement; returns an unchanged copy (the baseline).

All four methods are deterministic: the same input always gives the same
output. `seed` is part of the signature so every method — including future
stochastic ones (e.g. a deep model) — is called the same way; the
current four do not use it.

Every method returns an array the same length as its input.

KNOWN LIMITATION (measured in tests/test_enhancement.py): without a noise
reference, noisereduce estimates the noise from the recording itself. A
sustained vowel is steady, so its harmonics are taken for noise and gated
out: on a 5 dB noisy synthetic vowel both modes keep only ~4-7% of the
vowel's level and LOWER the SNR. Given a noise-only sample, the stationary
mode works (SI-SDR 5 -> 14 dB). The non-stationary mode ignores `noise_ref`
by design (it gates anything steady for ~2 s), so it stays unsuitable for
sustained vowels. This is the likely cause of Known Problem 5 (enhancement
lowering Component 2 prediction agreement).

This does NOT replace `degradation.py` (which synthetically damages clean
audio to study robustness) — this module does the opposite: it tries to
undo real-world damage on an incoming recording before Component 2/3 see it.
"""

import noisereduce as nr
import numpy as np
from scipy.signal import wiener

METHODS = ("noisereduce_nonstationary", "noisereduce_stationary", "wiener", "none")
WIENER_WINDOW = 3  # samples; scipy's default local window size


def _match_length(out: np.ndarray, n: int) -> np.ndarray:
    """Trim or zero-pad out to exactly n samples."""
    if len(out) >= n:
        return out[:n]
    return np.pad(out, (0, n - len(out)))


def enhance(y: np.ndarray, sr: int, method: str, seed: int,
            noise_ref: np.ndarray | None = None) -> np.ndarray:
    """Enhance a mono signal with the chosen method. Output length == input length.

    seed: accepted for a uniform interface; the current methods are deterministic.
    noise_ref: optional noise-only audio (same sr). Used by "noisereduce_stationary"
    as its noise profile; the other methods ignore it.
    """
    if method not in METHODS:
        raise ValueError(f"Unknown enhancement method {method!r}; choose from {METHODS}")
    y = np.asarray(y)
    if method == "none":
        return y.copy()
    if method == "wiener":
        out = wiener(y, mysize=WIENER_WINDOW)
    else:
        stationary = method == "noisereduce_stationary"
        y_noise = noise_ref if stationary else None   # non-stationary mode cannot use it
        out = nr.reduce_noise(y=y, sr=sr, stationary=stationary, y_noise=y_noise)
    # Digital silence gives 0/0 inside both scipy's Wiener filter and
    # noisereduce's non-stationary gate; replace those NaNs with 0 (silence).
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    return _match_length(out, len(y))

