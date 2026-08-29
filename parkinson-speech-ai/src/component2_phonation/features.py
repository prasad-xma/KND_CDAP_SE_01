"""Phonation feature extraction for Component 2 (phonation-based PD detection).

This is the single source of truth for turning a .wav file into the feature
vector used by the model. It MUST be used for both training and prediction —
the original Colab notebook computed jitter/shimmer/HNR one way during
training (via Praat/parselmouth) and a different, incompatible way during
prediction (via raw diff-based formulas on librosa output), which silently
made trained-model predictions on new recordings meaningless. Keeping one
function used everywhere prevents that class of bug from coming back.
"""

import numpy as np
import librosa
import parselmouth

from ..common.audio_io import ensure_wav

F0_MIN_HZ = 70
F0_MAX_HZ = 400

FEATURE_NAMES = [
    "mean_f0",
    "std_f0",
    "max_f0",
    "jitter",
    "shimmer",
    "hnr",
    "mean_rms",
    "std_rms",
    "mean_zcr",
    "std_zcr",
]


def extract_phonation_features(audio_path):
    """Extract the 10 phonation features used by the Component 2 baseline model.

    Returns a dict with keys matching FEATURE_NAMES, or None if no voiced
    frames could be detected (e.g. silent/corrupt file).
    """
    audio_path = ensure_wav(audio_path)
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    f0, _voiced_flag, _voiced_probs = librosa.pyin(
        y, fmin=F0_MIN_HZ, fmax=F0_MAX_HZ, sr=sr
    )
    valid_f0 = f0[~np.isnan(f0)]

    if len(valid_f0) == 0:
        return None

    mean_f0 = float(np.mean(valid_f0))
    std_f0 = float(np.std(valid_f0))
    max_f0 = float(np.max(valid_f0))

    rms = librosa.feature.rms(y=y)[0]
    mean_rms = float(np.mean(rms))
    std_rms = float(np.std(rms))

    zcr = librosa.feature.zero_crossing_rate(y)[0]
    mean_zcr = float(np.mean(zcr))
    std_zcr = float(np.std(zcr))

    sound = parselmouth.Sound(audio_path)
    pitch = sound.to_pitch(time_step=0.01, pitch_floor=F0_MIN_HZ, pitch_ceiling=F0_MAX_HZ)
    point_process = parselmouth.praat.call(pitch, "To PointProcess")

    jitter = parselmouth.praat.call(
        point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3
    )
    shimmer = parselmouth.praat.call(
        [sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6
    )

    harmonicity = sound.to_harmonicity_cc(time_step=0.01, minimum_pitch=F0_MIN_HZ)
    hnr = parselmouth.praat.call(harmonicity, "Get mean", 0, 0)

    return {
        "mean_f0": mean_f0,
        "std_f0": std_f0,
        "max_f0": max_f0,
        "jitter": jitter,
        "shimmer": shimmer,
        "hnr": hnr,
        "mean_rms": mean_rms,
        "std_rms": std_rms,
        "mean_zcr": mean_zcr,
        "std_zcr": std_zcr,
    }
