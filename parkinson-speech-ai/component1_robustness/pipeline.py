"""Component 1 end-to-end: one recording in, a gate decision and report out.

run_gate(audio_path, task, config) runs, in order:
    ensure_wav -> load (mono, config sample_rate) -> duration check (stop early on fail)
    -> quality before -> features before -> enhance -> quality after -> features after
    -> compare_features -> gate model decision

and writes to outputs/component1/<clip_id>/:
    raw.wav, enhanced.wav, waveform.png, spectrogram.png, report.json
(an early duration failure writes only raw.wav and report.json).

Which audio is judged and forwarded:
    features preserved     -> the gate judges ENHANCED audio; on PASS enhanced.wav is forwarded
    features not preserved -> enhancement altered the biomarkers, so the gate judges RAW audio;
                              on PASS raw.wav is forwarded
    FAIL                   -> nothing is forwarded; user_message says what to do

The report has no timestamps, so the same input and config give byte-identical report.json.
"""

import hashlib
import json
import math
import os
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from common.audio_io import ensure_wav
from component1_robustness.config import resolve_path
from component1_robustness.enhancement import enhance
from component1_robustness.features_check import compare_features, phonation_features
from component1_robustness.gate_models import (
    FAIL, PASS, gate_inputs, load_gate_model,
)
from component1_robustness.quality_metrics import check_duration
from component1_robustness.visualise import plot_spectrograms, plot_waveforms

TASKS = {"vowel": "component2", "ddk": "component3"}
# 24-bit PCM (~144 dB dynamic range, far beyond any phone microphone). Not 32-bit
# float: libsndfile adds a PEAK chunk containing a timestamp to float WAVs, which
# would make raw.wav / enhanced.wav differ on every run.
WAV_SUBTYPE = "PCM_24"

USER_MESSAGES = {
    "ok": "Recording accepted.",
    "too_short": "The recording is too short. Please record for at least {min:.0f} seconds.",
    "too_long": "The recording is too long. Please keep it under {max:.0f} seconds.",
    "clipped": "The recording is distorted (too loud). Please hold the phone a little further away and record again.",
    "no_voice": "No voice was detected. Please make sure you are speaking into the microphone and record again.",
    "low_snr": "There is too much background noise. Please record again in a quieter room.",
    "low_quality": "The recording quality is too low. Please record again in a quieter room, close to the microphone.",
}

REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "clip_id", "task", "gate_model", "decision", "quality_score", "reason", "duration_s",
        "quality_before", "quality_after", "features_before", "features_after", "feature_preserved",
        "audio_for_next_stage", "audio_choice", "next_component", "user_message", "input_sha256",
        "config_version",
    ],
    "properties": {
        "clip_id": {"type": "string", "minLength": 1},
        "task": {"enum": list(TASKS)},
        "gate_model": {"type": "string"},
        "decision": {"enum": [PASS, FAIL]},
        "quality_score": {"type": "number", "minimum": 0, "maximum": 100},
        "reason": {"type": "string"},
        "duration_s": {"type": "number", "minimum": 0},
        "quality_before": {"type": ["object", "null"]},
        "quality_after": {"type": ["object", "null"]},
        "features_before": {"type": ["object", "null"]},
        "features_after": {"type": ["object", "null"]},
        "feature_preserved": {"type": ["object", "null"],
                              "properties": {"per_feature": {"type": "object"},
                                             "preserved": {"type": "boolean"}}},
        "audio_for_next_stage": {"type": ["string", "null"]},
        "audio_choice": {"enum": ["enhanced", "raw", None]},
        "next_component": {"enum": [*TASKS.values(), None]},
        "user_message": {"type": "string", "minLength": 1},
        "input_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "config_version": {"type": "string"},
    },
}


# --- Small helpers -----------------------------------------------------------------

def sha256_file(path: str | Path) -> str:
    """Hex SHA-256 of a file's bytes (identifies the exact input recording)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def make_clip_id(audio_path: str | Path, input_sha256: str) -> str:
    """File stem + first 8 hex digits of its hash: readable and unique per content."""
    return f"{Path(audio_path).stem}_{input_sha256[:8]}"


def load_standardised(audio_path: str | Path) -> tuple[np.ndarray, int]:
    """Any format -> mono float32 at the recording's OWN sample rate. Returns (y, sr).

    No resampling: Component 2's ZCR and pitch features depend on sample rate, so
    resampling here changed its predictions. Deletes the temporary WAV if one was made.
    """
    wav_path = ensure_wav(str(audio_path))
    try:
        y, sr = librosa.load(wav_path, sr=None, mono=True)
    finally:
        if os.path.abspath(wav_path) != os.path.abspath(str(audio_path)):
            os.remove(wav_path)
    return y, sr


def json_safe(value):
    """Make a value JSON-standard: numpy -> Python, NaN/inf -> None, recursively."""
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    return value


def write_report(report: dict, path: Path) -> None:
    """Write report.json deterministically (fixed key order, UTF-8, trailing newline)."""
    text = json.dumps(json_safe(report), indent=2, ensure_ascii=False, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def user_message(reason: str, config: dict) -> str:
    return USER_MESSAGES.get(reason, "Please record again.").format(
        min=config["min_duration_s"], max=config["max_duration_s"])


# --- The pipeline ------------------------------------------------------------------

def run_gate(audio_path: str | Path, task: str, config: dict, gate=None) -> dict:
    """Run Component 1 on one recording; write the output folder and return the report dict.

    gate can be passed in to reuse it across many clips; by default it is
    config["gate_model"].
    """
    if task not in TASKS:
        raise ValueError(f"task must be one of {list(TASKS)}, got {task!r}")
    gate = gate or load_gate_model(config["gate_model"], config)

    input_sha256 = sha256_file(audio_path)
    clip_id = make_clip_id(audio_path, input_sha256)
    out_dir = resolve_path(config, "outputs") / clip_id
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path, enhanced_path = out_dir / "raw.wav", out_dir / "enhanced.wav"

    y_raw, sr = load_standardised(audio_path)   # native sample rate, no resampling
    sf.write(raw_path, y_raw, sr, subtype=WAV_SUBTYPE)

    report = {
        "clip_id": clip_id, "task": task, "gate_model": gate.name,
        "decision": FAIL, "quality_score": 0.0, "reason": "",
        "duration_s": len(y_raw) / sr,
        "quality_before": None, "quality_after": None,
        "features_before": None, "features_after": None, "feature_preserved": None,
        "audio_for_next_stage": None, "audio_choice": None, "next_component": None,
        "user_message": "", "input_sha256": input_sha256, "config_version": str(config["config_version"]),
    }

    # Duration first: a clip of the wrong length is not worth enhancing.
    duration_ok, duration_reason = check_duration(y_raw, sr, config["min_duration_s"], config["max_duration_s"])
    if not duration_ok:
        report.update(reason=duration_reason, user_message=user_message(duration_reason, config))
        write_report(report, out_dir / "report.json")
        return json_safe(report)

    quality_before = gate_inputs(y_raw, sr, config)
    features_before = phonation_features(y_raw, sr)

    y_enh = enhance(y_raw, sr, config["enhancement_method"], config["seed"])
    sf.write(enhanced_path, y_enh, sr, subtype=WAV_SUBTYPE)

    quality_after = gate_inputs(y_enh, sr, config)
    features_after = phonation_features(y_enh, sr)
    preservation = compare_features(features_before, features_after, config["feature_tolerances"])

    use_enhanced = preservation["preserved"]
    judged = quality_after if use_enhanced else quality_before
    decision = gate.predict(judged)

    before = (quality_before["estimated_snr_db"], quality_before["method"])
    after = (quality_after["estimated_snr_db"], quality_after["method"])
    plot_waveforms(y_raw, y_enh, sr, out_dir / "waveform.png", before=before, after=after)
    plot_spectrograms(y_raw, y_enh, sr, out_dir / "spectrogram.png", before=before, after=after)

    report.update(
        decision=decision["decision"], quality_score=decision["quality_score"], reason=decision["reason"],
        quality_before=quality_before, quality_after=quality_after,
        features_before=features_before, features_after=features_after, feature_preserved=preservation,
        user_message=user_message(decision["reason"], config),
    )
    if decision["decision"] == PASS:
        report.update(
            audio_choice="enhanced" if use_enhanced else "raw",
            audio_for_next_stage=str(enhanced_path if use_enhanced else raw_path),
            next_component=TASKS[task],
        )
    write_report(report, out_dir / "report.json")
    return json_safe(report)
