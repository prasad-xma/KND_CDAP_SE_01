"""DDK (diadochokinetic) feature extraction for Component 3.

Single source of truth for turning a "pa"/"ta" repetition recording into the
feature vector used by the model — mirrors Component 2's features.py in
spirit (one function, used identically for training and prediction).

Features capture what the research plan describes for DDK: rate, timing
variability (rhythm regularity), pause characteristics, and articulation
(spectral/MFCC) — not lexical content, since "pa"/"ta" isn't language-specific.
"""

import numpy as np
import librosa

from ..common.audio_io import ensure_wav

FEATURE_NAMES = [
    "ddk_rate",
    "mean_ioi",
    "std_ioi",
    "cv_ioi",
    "num_pauses",
    "pause_ratio",
    "mean_spectral_centroid",
    "std_spectral_centroid",
    "mean_spectral_bandwidth",
    "mean_mfcc1",
    "mean_mfcc2",
    "mean_mfcc3",
]

MIN_ONSETS = 3  # need at least 2 intervals to compute meaningful IOI stats
SILENCE_TOP_DB = 30
MIN_PAUSE_SEC = 0.05


def extract_ddk_features(audio_path):
    """Extract DDK timing/rhythm/articulation features from a repeated-syllable recording.

    Returns a dict with keys matching FEATURE_NAMES, or None if too few
    syllable onsets were detected to compute timing statistics.
    """
    audio_path = ensure_wav(audio_path)
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    duration = len(y) / sr

    onset_times = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=False)
    if len(onset_times) < MIN_ONSETS:
        return None

    ioi = np.diff(onset_times)
    mean_ioi = float(np.mean(ioi))
    std_ioi = float(np.std(ioi))
    cv_ioi = float(std_ioi / mean_ioi) if mean_ioi > 0 else np.nan
    ddk_rate = float(len(onset_times) / duration)

    intervals = librosa.effects.split(y, top_db=SILENCE_TOP_DB)
    pause_durations = []
    for i in range(1, len(intervals)):
        gap_samples = intervals[i][0] - intervals[i - 1][1]
        gap_sec = gap_samples / sr
        if gap_sec >= MIN_PAUSE_SEC:
            pause_durations.append(gap_sec)
    num_pauses = len(pause_durations)
    pause_ratio = float(sum(pause_durations) / duration) if duration > 0 else 0.0

    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=4)

    return {
        "ddk_rate": ddk_rate,
        "mean_ioi": mean_ioi,
        "std_ioi": std_ioi,
        "cv_ioi": cv_ioi,
        "num_pauses": float(num_pauses),
        "pause_ratio": pause_ratio,
        "mean_spectral_centroid": float(np.mean(spectral_centroid)),
        "std_spectral_centroid": float(np.std(spectral_centroid)),
        "mean_spectral_bandwidth": float(np.mean(spectral_bandwidth)),
        "mean_mfcc1": float(np.mean(mfcc[1])),
        "mean_mfcc2": float(np.mean(mfcc[2])),
        "mean_mfcc3": float(np.mean(mfcc[3])),
    }
