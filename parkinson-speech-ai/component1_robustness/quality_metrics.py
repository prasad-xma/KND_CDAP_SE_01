"""Signal-quality measurements for Component 1 (no pass/fail decisions here).

quality_gate.py decides pass/fail; this module only MEASURES. Every function
works on an in-memory signal (y, sr); the two SNR/HNR estimators also accept
a file path, for backward compatibility.

Two SNR-style estimators, picked per recording, because one metric doesn't
work for both task types:
  - Silence-based blind SNR (loudest frames vs quietest frames) — works for
    DDK ("pa-ta-ka") recordings, which have real pauses to measure a noise
    floor from.
  - HNR (harmonics-to-noise ratio, via Parselmouth/Praat — the same measure
    Component 2 uses as a feature) — used when no real silence is present,
    which is normal for a tightly trimmed sustained vowel ("aaaa").
    A clip with no silence has no genuine noise floor, so the "quietest 10%
    of frames" would just be quiet vowel energy, not noise.
"""

from pathlib import Path

import librosa
import numpy as np
import parselmouth

EPS = 1e-12

# Silence-based SNR
FRAME_LENGTH = 2048
HOP_LENGTH = 512
NOISE_FLOOR_PERCENTILE = 10
SIGNAL_PERCENTILE = 90
SILENCE_TOP_DB = 30            # frames this far below the peak count as silence
MIN_SILENCE_FRACTION = 0.05    # need >= 5% real silence to trust the silence-based SNR
MAX_SNR_DB = 60.0              # returned when the noise floor is digital silence

# HNR
F0_MIN_HZ = 70

# Voice activity
VAD_TOP_DB = 30                # active = within 30 dB of the loudest frame...
VAD_ABS_FLOOR_DBFS = -60.0     # ...AND above -60 dBFS (so pure silence has 0% activity)

# Clipping
CLIP_THRESHOLD = 0.99

AudioSource = str | Path | np.ndarray


# --- Basic measurements ------------------------------------------------------

def duration_s(y: np.ndarray, sr: int) -> float:
    """Length of the signal in seconds."""
    return len(y) / sr


def check_duration(y: np.ndarray, sr: int, min_s: float, max_s: float) -> tuple[bool, str]:
    """Return (ok, reason) where reason is "ok", "too_short" or "too_long". Limits are inclusive."""
    d = duration_s(y, sr)
    if d < min_s:
        return False, "too_short"
    if d > max_s:
        return False, "too_long"
    return True, "ok"


def mean_level_dbfs(y: np.ndarray) -> float:
    """Overall RMS level in dB relative to full scale (1.0)."""
    rms = np.sqrt(np.mean(y ** 2) + EPS)
    return float(20 * np.log10(rms + EPS))


def clipping_pct(y: np.ndarray, threshold: float = CLIP_THRESHOLD) -> float:
    """Percentage of samples whose magnitude is at or above threshold (near full scale)."""
    if len(y) == 0:
        return 0.0
    return float(100.0 * np.mean(np.abs(y) >= threshold))


def _frame_rms_db(y: np.ndarray) -> np.ndarray:
    """Per-frame RMS level in dBFS."""
    rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    return 20 * np.log10(rms + EPS)


def voice_activity_pct(y: np.ndarray, sr: int) -> float:
    """Percentage of frames that contain sound (energy-based voice activity).

    A frame is active when it is within VAD_TOP_DB of the loudest frame AND
    above the absolute floor VAD_ABS_FLOOR_DBFS. sr is accepted for a
    consistent signature; frame sizes are fixed in samples.
    """
    frame_db = _frame_rms_db(y)
    if len(frame_db) == 0:
        return 0.0
    threshold = max(frame_db.max() - VAD_TOP_DB, VAD_ABS_FLOOR_DBFS)
    return float(100.0 * np.mean(frame_db > threshold))


# --- SNR / HNR estimators ----------------------------------------------------

def has_usable_silence(y: np.ndarray, sr: int) -> bool:
    """True if at least MIN_SILENCE_FRACTION of the clip is silence (> SILENCE_TOP_DB below peak)."""
    non_silent = librosa.effects.split(y, top_db=SILENCE_TOP_DB)
    silent_samples = len(y) - sum(end - start for start, end in non_silent)
    return bool((silent_samples / len(y)) >= MIN_SILENCE_FRACTION)


def silence_based_snr(y: np.ndarray) -> float:
    """Blind SNR (dB): 90th-percentile frame RMS over 10th-percentile frame RMS."""
    rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    rms = rms[rms > 0]
    if len(rms) == 0:
        return -np.inf
    noise_floor = np.percentile(rms, NOISE_FLOOR_PERCENTILE)
    signal_level = np.percentile(rms, SIGNAL_PERCENTILE)
    if noise_floor <= 1e-9:
        return MAX_SNR_DB
    return float(20 * np.log10(signal_level / noise_floor))


def _to_sound(source: AudioSource, sr: int | None) -> parselmouth.Sound:
    """Build a Praat Sound from a file path, or from an array plus its sample rate."""
    if isinstance(source, (str, Path)):
        return parselmouth.Sound(str(source))
    if sr is None:
        raise ValueError("sr is required when passing an array")
    return parselmouth.Sound(np.asarray(source, dtype=np.float64), sampling_frequency=sr)


def hnr(source: AudioSource, sr: int | None = None) -> float:
    """Mean harmonics-to-noise ratio (dB) via Praat. source = path, or array with sr.

    Returns -inf when Praat finds no periodic frames.
    """
    sound = _to_sound(source, sr)
    harmonicity = sound.to_harmonicity_cc(time_step=0.01, minimum_pitch=F0_MIN_HZ)
    value = parselmouth.praat.call(harmonicity, "Get mean", 0, 0)
    return float(value) if not np.isnan(value) else -np.inf


def estimate_quality_db(source: AudioSource, sr: int | None = None) -> tuple[float, str]:
    """Return (estimate_db, method); method is "silence_snr" or "hnr".

    source = WAV path (as before), or an array with its sample rate.
    """
    if isinstance(source, (str, Path)):
        y, sr = librosa.load(str(source), sr=None, mono=True)
    else:
        if sr is None:
            raise ValueError("sr is required when passing an array")
        y = np.asarray(source, dtype=np.float32)
    if has_usable_silence(y, sr):
        return silence_based_snr(y), "silence_snr"
    return hnr(source if isinstance(source, (str, Path)) else y, sr), "hnr"


# --- All metrics together ----------------------------------------------------

def compute_quality(y: np.ndarray, sr: int) -> dict[str, float | str]:
    """All quality metrics for one signal, as a flat dict."""
    estimate_db, method = estimate_quality_db(y, sr)
    return {
        "duration_s": duration_s(y, sr),
        "level_dbfs": mean_level_dbfs(y),
        "clipping_pct": clipping_pct(y),
        "voice_activity_pct": voice_activity_pct(y, sr),
        "estimated_snr_db": estimate_db,
        "method": method,
    }
