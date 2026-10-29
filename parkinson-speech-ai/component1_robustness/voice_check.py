"""Voice presence check: is someone actually speaking in the recording?

Why this exists: real laptop-mic takes with nobody speaking (steady room noise,
fan, mains hum) passed the old SNR/HNR rule, or were told "too much background
noise" when the truth was "no voice". Config v1.2-v1.4 tried Praat voicing
(rule A) and voice activity after noise reduction (rule B); on labelled real
takes both failed: room hum looked up to 87% "voiced", and noise reduction also
removed the user's real sustained vowel.

Rule (config v1.5), on the RAW audio:
    speech_band_contrast_db >= min_speech_band_contrast_db (6 dB)  -> voice present
    otherwise the take is flat (no voice starting/stopping):
        level_dbfs <  no_voice_max_level_dbfs (-30 dBFS) -> "no_voice"  (quiet room, nobody spoke)
        level_dbfs >= no_voice_max_level_dbfs             -> "low_snr"   (loud steady noise drowned the voice)

Labelled real takes, 2026-10-28 (laptop mic, Chrome): 10 silent takes had
contrast 2.3-3.4 dB at -36 to -43 dBFS; 3 voice takes had 11.1-15.0 dB.

The pipeline applies this to a PASS and to a quality FAIL (low_snr / low_quality),
so a silent take is told "no voice" instead of "too noisy". Duration, clipping and
the gate's own "no_voice" precheck are left as they are.

Thresholds are PLACEHOLDERS calibrated on one device; recheck on phones (Phase 2).
"""

DEFAULT_VOICE_CHECK = {
    "min_speech_band_contrast_db": 6.0,
    "no_voice_max_level_dbfs": -30.0,
}

# Gate reasons the voice check may replace: a quality FAIL on a take with no voice
# is really "no voice". Hard-rule reasons (too_short, too_long, clipped) are kept.
OVERRIDABLE_REASONS = {"ok", "low_snr", "low_quality"}


def voice_check_config(config: dict) -> dict:
    """config["voice_check"] merged over DEFAULT_VOICE_CHECK."""
    return {**DEFAULT_VOICE_CHECK, **(config.get("voice_check") or {})}


def check_voice_presence(quality_raw: dict, config: dict) -> dict:
    """Voice presence from the raw audio's quality metrics (a compute_quality() dict).

    Returns the measured values, the thresholds, "passed", and "fail_reason"
    ("no_voice" or "low_snr" when not passed, else None).
    """
    c = voice_check_config(config)
    contrast = float(quality_raw["speech_band_contrast_db"])
    level = float(quality_raw["level_dbfs"])
    passed = contrast >= c["min_speech_band_contrast_db"]
    if passed:
        fail_reason = None
    elif level < c["no_voice_max_level_dbfs"]:
        fail_reason = "no_voice"
    else:
        fail_reason = "low_snr"
    return {
        "speech_band_contrast_db": contrast,
        "level_dbfs": level,
        "min_speech_band_contrast_db": float(c["min_speech_band_contrast_db"]),
        "no_voice_max_level_dbfs": float(c["no_voice_max_level_dbfs"]),
        "passed": bool(passed),
        "fail_reason": fail_reason,
    }
