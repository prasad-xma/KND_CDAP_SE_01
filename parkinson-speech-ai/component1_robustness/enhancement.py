"""Real audio enhancement/cleanup — the piece the proposal calls "Stage 4:
Enhancement / Cleanup Algorithms" (slide 17).

enhance(y, sr, method, seed, noise_ref=None) works on in-memory arrays. Methods:
  - "noisereduce_nonstationary": spectral gating that adapts to noise that
    changes over the recording (phone background noise is rarely constant).
  - "noisereduce_stationary": spectral gating with one fixed noise profile,
    taken from `noise_ref` (a noise-only stretch of audio) when given.
  - "wiener": classic Wiener filter (scipy.signal.wiener) in the time domain.
  - "highpass": zero-phase Butterworth high-pass at `highpass_hz` (default 80 Hz).
    Removes mains hum and fan/handling rumble below the voice; it never touches
    the vowel's harmonics (F0 >= 70 Hz), so the biomarkers are left alone.
  - "none": no enhancement; returns an unchanged copy (the baseline).

noisereduce options (config `enhancement:` section, read by pipeline.py):
  - prop_decrease (0-1): how much of the estimated noise to remove; 1.0 = all
    (noisereduce default), lower = gentler, keeps more of the voice.
  - noise_ref: noise-only audio for the stationary mode. noise_reference()
    builds it from the take itself: the samples OUTSIDE the voiced stretches
    found by the task check's pitch track (e.g. before the user starts "aaaa").

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
from scipy.signal import butter, sosfiltfilt, wiener

METHODS = ("noisereduce_nonstationary", "noisereduce_stationary", "wiener", "highpass", "none")
WIENER_WINDOW = 3  # samples; scipy's default local window size
HIGHPASS_ORDER = 4
DEFAULT_HIGHPASS_HZ = 80.0
NOISE_REF_MARGIN_S = 0.05     # keep this far from any voiced stretch
MIN_NOISE_REF_S = 0.25        # shorter than this -> not enough to profile the noise


def _match_length(out: np.ndarray, n: int) -> np.ndarray:
    """Trim or zero-pad out to exactly n samples."""
    if len(out) >= n:
        return out[:n]
    return np.pad(out, (0, n - len(out)))


def noise_reference(y: np.ndarray, sr: int) -> np.ndarray | None:
    """Noise-only samples of a take: everything outside its voiced stretches.

    Uses the task check's pitch track (task_check.voiced_runs), with a small margin
    around each stretch. None when there is less than MIN_NOISE_REF_S of it (e.g. the
    user started speaking immediately), so the caller can fall back.
    """
    from component1_robustness.task_check import TIME_STEP_S, pitch_track, voiced_runs

    y = np.asarray(y, dtype=np.float64)
    keep = np.ones(len(y), dtype=bool)
    margin = int(NOISE_REF_MARGIN_S * sr)
    for first, last in voiced_runs(pitch_track(y, sr)):
        start = max(int(first * TIME_STEP_S * sr) - margin, 0)
        stop = min(int((last + 1) * TIME_STEP_S * sr) + margin, len(y))
        keep[start:stop] = False
    if keep.sum() < MIN_NOISE_REF_S * sr:
        return None
    return y[keep]


def enhance(y: np.ndarray, sr: int, method: str, seed: int,
            noise_ref: np.ndarray | None = None, prop_decrease: float = 1.0,
            highpass_hz: float = DEFAULT_HIGHPASS_HZ) -> np.ndarray:
    """Enhance a mono signal with the chosen method. Output length == input length.

    seed: accepted for a uniform interface; the current methods are deterministic.
    noise_ref: optional noise-only audio (same sr). Used by "noisereduce_stationary"
    as its noise profile; the other methods ignore it.
    prop_decrease: share of the estimated noise noisereduce removes (1.0 = all).
    highpass_hz: cut-off for "highpass".
    """
    if method not in METHODS:
        raise ValueError(f"Unknown enhancement method {method!r}; choose from {METHODS}")
    y = np.asarray(y)
    if method == "none":
        return y.copy()
    if method == "highpass":
        sos = butter(HIGHPASS_ORDER, highpass_hz, btype="highpass", fs=sr, output="sos")
        out = sosfiltfilt(sos, y)
    elif method == "wiener":
        out = wiener(y, mysize=WIENER_WINDOW)
    else:
        stationary = method == "noisereduce_stationary"
        y_noise = noise_ref if stationary else None   # non-stationary mode cannot use it
        out = nr.reduce_noise(y=y, sr=sr, stationary=stationary, y_noise=y_noise,
                              prop_decrease=prop_decrease)
    # Digital silence gives 0/0 inside both scipy's Wiener filter and
    # noisereduce's non-stationary gate; replace those NaNs with 0 (silence).
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    return _match_length(out, len(y))

