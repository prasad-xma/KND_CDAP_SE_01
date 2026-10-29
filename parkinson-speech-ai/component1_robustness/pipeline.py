"""Component 1 end-to-end: one recording in, a gate decision and report out.

run_gate(audio_path, task, config) runs, in order:
    ensure_wav -> load (mono, config sample_rate) -> duration check (stop early on fail)
    -> quality before -> features before -> enhance -> quality after -> features after
    -> compare_features -> gate model decision -> voice presence check (voice_check.py)
    -> task check (task_check.py, when enabled in the config)

and writes to outputs/component1/<clip_id>/:
    raw.wav, enhanced.wav, waveform.png, spectrogram.png, report.json
(an early duration failure writes only raw.wav and report.json).

Which audio is judged and forwarded:
    features preserved     -> the gate judges ENHANCED audio; on PASS enhanced.wav is forwarded
    features not preserved -> enhancement altered the biomarkers, so the gate judges RAW audio;
                              on PASS raw.wav is forwarded
    FAIL                   -> nothing is forwarded; user_message says what to do

Voice presence (voice_check.py): if the raw take is flat in the speech band (nobody
started or stopped speaking), a PASS or quality FAIL becomes "no_voice" in a quiet room,
or "low_snr" when loud steady noise drowned the voice.

Enhancement policy (config `enhancement:` section, v1.8; absent = always enhance, as before):
    skip_if_contrast_db_at_least  a take this clean is not processed at all: enhanced.wav is
                                  a copy of raw.wav and raw.wav is forwarded. Real app takes
                                  did not need cleaning, and cleaning damaged their biomarkers.
    noise_sample                  for noisereduce_stationary: build the noise profile from the
                                  take's own non-voiced parts (enhancement.noise_reference).
                                  Too little non-voiced audio -> fallback_method is used instead.
    prop_decrease, highpass_hz    passed to enhancement.enhance().
The report then has an "enhancement" key saying what was done and why.

Task check (task_check.py, config task_check.enabled): a good-quality take that is not
the task (e.g. speech or gibberish instead of one steady "aaaa") becomes "wrong_task".
It only replaces a PASS: a take that already failed on quality keeps that message, since
it has to be re-recorded anyway. Without a task_check section the report has no
"task_check" key, so older configs give exactly the same report.json as before.

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
from component1_robustness.enhancement import enhance, noise_reference
from component1_robustness.features_check import compare_features, ddk_features, phonation_features
from component1_robustness.gate_models import (
    FAIL, PASS, gate_inputs, load_gate_model,
)
from component1_robustness.quality_metrics import check_duration
from component1_robustness.task_check import check_task
from component1_robustness.visualise import plot_spectrograms, plot_waveforms
from component1_robustness.voice_check import OVERRIDABLE_REASONS, check_voice_presence

TASKS = {"vowel": "component2", "ddk": "component3"}
# Biomarkers that must survive enhancement: the features of the component that receives the audio.
TASK_FEATURES = {"vowel": (phonation_features, "feature_tolerances"),
                 "ddk": (ddk_features, "ddk_feature_tolerances")}
# 24-bit PCM (~144 dB dynamic range, far beyond any phone microphone). Not 32-bit
# float: libsndfile adds a PEAK chunk containing a timestamp to float WAVs, which
# would make raw.wav / enhanced.wav differ on every run.
WAV_SUBTYPE = "PCM_24"

USER_MESSAGES = {
    "ok": "Recording accepted.",
    "too_short": "The recording is too short. Please record for at least {min:g} seconds.",
    "too_long": "The recording is too long. Please keep it under {max:g} seconds.",
    "clipped": "The recording is distorted (too loud). Please hold the phone a little further away and record again.",
    "no_voice": "No voice was detected. Please make sure you are speaking into the microphone and record again.",
    "low_snr": "There is too much background noise. Please record again in a quieter room.",
    "low_quality": "The recording quality is too low. Please record again in a quieter room, close to the microphone.",
    "wrong_task": "We didn't hear one steady \"aaaa\". Please take a breath and say \"aaaa\" in one long, steady sound until the timer ends.",
}

REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "clip_id", "task", "gate_model", "decision", "quality_score", "reason", "duration_s",
        "quality_before", "quality_after", "features_before", "features_after", "feature_preserved",
        "audio_for_next_stage", "audio_choice", "next_component", "user_message", "input_sha256",
        "config_version", "voice_check",
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
        "voice_check": {"type": ["object", "null"]},
        "task_check": {"type": ["object", "null"]},   # optional: only when task_check is enabled
        "enhancement": {"type": ["object", "null"]},  # optional: only with an `enhancement:` config section
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


def enhance_take(y_raw: np.ndarray, sr: int, contrast_db: float, config: dict) -> tuple[np.ndarray, dict | None]:
    """(enhanced signal, what was done). Without an `enhancement:` section: always enhance, info None."""
    method, seed = config["enhancement_method"], config["seed"]
    policy = config.get("enhancement")
    if not policy:
        return enhance(y_raw, sr, method, seed), None
    skip_db = policy.get("skip_if_contrast_db_at_least")
    info = {"configured_method": method, "applied": True, "method_used": method,
            "skip_if_contrast_db_at_least": skip_db, "speech_band_contrast_db": float(contrast_db),
            "noise_sample_s": None, "note": None}
    if skip_db is not None and contrast_db >= skip_db:
        info.update(applied=False, method_used="none", note="clean enough: not processed")
        return y_raw.copy(), info
    options = {"prop_decrease": float(policy.get("prop_decrease", 1.0)),
               "highpass_hz": float(policy.get("highpass_hz", 80.0))}
    if method == "noisereduce_stationary" and policy.get("noise_sample", False):
        noise_ref = noise_reference(y_raw, sr)
        if noise_ref is None:
            method = policy.get("fallback_method", "none")
            info.update(method_used=method, note="no noise-only part in the take: fallback used")
        else:
            options["noise_ref"] = noise_ref
            info["noise_sample_s"] = len(noise_ref) / sr
    return enhance(y_raw, sr, method, seed, **options), info


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
        "voice_check": None,
    }

    # Duration first: a clip of the wrong length is not worth enhancing.
    duration_ok, duration_reason = check_duration(y_raw, sr, config["min_duration_s"], config["max_duration_s"])
    if not duration_ok:
        report.update(reason=duration_reason, user_message=user_message(duration_reason, config))
        write_report(report, out_dir / "report.json")
        return json_safe(report)

    extract_features, tolerance_key = TASK_FEATURES[task]
    quality_before = gate_inputs(y_raw, sr, config)
    features_before = extract_features(y_raw, sr)

    y_enh, enhancement = enhance_take(y_raw, sr, quality_before["speech_band_contrast_db"], config)
    sf.write(enhanced_path, y_enh, sr, subtype=WAV_SUBTYPE)
    applied = enhancement is None or enhancement["applied"]

    if applied:
        quality_after = gate_inputs(y_enh, sr, config)
        features_after = extract_features(y_enh, sr)
    else:   # not processed: the "after" audio is the raw audio
        quality_after, features_after = quality_before, features_before
    preservation = compare_features(features_before, features_after, config[tolerance_key])

    use_enhanced = applied and preservation["preserved"]
    judged = quality_after if use_enhanced else quality_before
    decision = gate.predict(judged)

    # Voice presence, on the raw audio: the gate judges quality, not whether anyone is
    # speaking. A flat take is "no_voice" (quiet room) or "low_snr" (loud steady noise),
    # replacing a PASS or a quality FAIL. Duration/clipping/precheck reasons are kept.
    voice_check = check_voice_presence(quality_before, config)
    if not voice_check["passed"] and decision["reason"] in OVERRIDABLE_REASONS:
        decision = {"decision": FAIL, "quality_score": 0.0, "reason": voice_check["fail_reason"]}

    # Task check, on the raw audio: a good-quality take that is not the task (speech or
    # gibberish instead of one held "aaaa") is "wrong_task". Only a PASS is replaced.
    task_check = check_task(y_raw, sr, task, config)
    if task_check is not None and not task_check["passed"] and decision["decision"] == PASS:
        decision = {"decision": FAIL, "quality_score": 0.0, "reason": task_check["fail_reason"]}

    before = (quality_before["estimated_snr_db"], quality_before["method"])
    after = (quality_after["estimated_snr_db"], quality_after["method"])
    plot_waveforms(y_raw, y_enh, sr, out_dir / "waveform.png", before=before, after=after)
    plot_spectrograms(y_raw, y_enh, sr, out_dir / "spectrogram.png", before=before, after=after)

    report.update(
        decision=decision["decision"], quality_score=decision["quality_score"], reason=decision["reason"],
        quality_before=quality_before, quality_after=quality_after,
        features_before=features_before, features_after=features_after, feature_preserved=preservation,
        user_message=user_message(decision["reason"], config), voice_check=voice_check,
    )
    if task_check is not None:
        report["task_check"] = task_check
    if enhancement is not None:
        report["enhancement"] = enhancement
    if decision["decision"] == PASS:
        report.update(
            audio_choice="enhanced" if use_enhanced else "raw",
            audio_for_next_stage=str(enhanced_path if use_enhanced else raw_path),
            next_component=TASKS[task],
        )
    write_report(report, out_dir / "report.json")
    return json_safe(report)
