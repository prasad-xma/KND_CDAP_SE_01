"""Voice presence check (config v1.5): speech-band contrast + level, on the raw audio.

Real-recording evidence (laptop mic through the app, 2026-10-28, labelled by the user):
  tests/data/real_no_speech/  6 takes, mic open, nobody speaking  -> must FAIL "no_voice"
                              (the old SNR/HNR rule passed 3 of the first 4, and told
                              later ones "too much background noise")
  tests/data/real_voice/      3 takes of the user's real voice     -> must PASS
                              ("aaaa" x2, "pa-ta-ka" x1; the old HNR rule failed all 3)
"""

from pathlib import Path

import numpy as np
import pytest

from component1_robustness import voice_check
from component1_robustness.config import load_config
from component1_robustness.pipeline import run_gate
from conftest import gate_config, make_vowel, write_wav

SR = 16000
DATA = Path(__file__).parent / "data"
REAL_NO_SPEECH = sorted((DATA / "real_no_speech").glob("*.wav"))
REAL_VOICE = sorted((DATA / "real_voice").glob("*.wav"))


def _task(path: Path) -> str:
    return "ddk" if path.stem.startswith("ddk") else "vowel"


# --- The rule ------------------------------------------------------------------------

@pytest.mark.parametrize("contrast,level,passed,reason", [
    (11.0, -35.0, True, None),          # real voice
    (6.0, -40.0, True, None),           # threshold is inclusive
    (5.9, -40.0, False, "no_voice"),    # flat and quiet: nobody spoke
    (2.4, -38.0, False, "no_voice"),    # the real silent takes
    (2.4, -20.0, False, "low_snr"),     # flat but loud: steady noise drowned the voice
    (2.4, -30.0, False, "low_snr"),     # level threshold: quieter than -30 dBFS is no_voice
])
def test_rule(contrast, level, passed, reason):
    result = voice_check.check_voice_presence(
        {"speech_band_contrast_db": contrast, "level_dbfs": level}, load_config())
    assert result["passed"] is passed
    assert result["fail_reason"] == reason


def test_config_defaults_fill_missing_keys():
    merged = voice_check.voice_check_config({"voice_check": {"min_speech_band_contrast_db": 8.0}})
    assert merged["min_speech_band_contrast_db"] == 8.0
    assert merged["no_voice_max_level_dbfs"] == voice_check.DEFAULT_VOICE_CHECK["no_voice_max_level_dbfs"]


# --- Through the pipeline ----------------------------------------------------------------

def test_quiet_steady_hum_is_no_voice(tmp_path):
    """Mains-like hum (110 Hz + harmonics) at about -45 dBFS with nobody speaking."""
    t = np.arange(SR * 4) / SR
    hum = sum((0.008 / k) * np.sin(2 * np.pi * 110 * k * t) for k in range(1, 6))
    y = hum + 1e-3 * np.random.default_rng(3).standard_normal(len(t))
    report = run_gate(write_wav(tmp_path, "hum.wav", y), "vowel", gate_config(tmp_path))
    assert (report["decision"], report["reason"]) == ("FAIL", "no_voice")
    assert "No voice" in report["user_message"]
    assert report["audio_for_next_stage"] is None


def test_loud_steady_noise_is_low_snr(tmp_path):
    y = 0.1 * np.random.default_rng(4).standard_normal(SR * 4)
    report = run_gate(write_wav(tmp_path, "noise.wav", y), "vowel", gate_config(tmp_path))
    assert (report["decision"], report["reason"]) == ("FAIL", "low_snr")
    assert "background noise" in report["user_message"]


def test_hard_rule_reasons_are_kept(tmp_path):
    """A clipped steady tone is flat, but "clipped" is the more useful message."""
    y = np.clip(4.0 * make_vowel(), -1.0, 1.0)
    report = run_gate(write_wav(tmp_path, "c.wav", y), "vowel", gate_config(tmp_path))
    assert report["reason"] == "clipped"


# --- Real recordings ------------------------------------------------------------------

@pytest.mark.parametrize("path", REAL_NO_SPEECH, ids=lambda p: p.stem)
def test_real_recordings_with_nobody_speaking_are_no_voice(tmp_path, path):
    report = run_gate(str(path), _task(path), gate_config(tmp_path))
    assert (report["decision"], report["reason"]) == ("FAIL", "no_voice"), report["voice_check"]


@pytest.mark.parametrize("path", REAL_VOICE, ids=lambda p: p.stem)
def test_real_voice_recordings_pass(tmp_path, path):
    report = run_gate(str(path), _task(path), gate_config(tmp_path))
    assert report["decision"] == "PASS", (report["reason"], report["voice_check"])
