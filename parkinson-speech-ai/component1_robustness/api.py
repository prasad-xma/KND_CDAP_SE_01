"""Standalone HTTP server for Component 1 (audio quality gate), in the same
style as component2_phonation/api.py, so the app can check a recording before
sending it on.

Run from `parkinson-speech-ai/`:
    uvicorn component1_robustness.api:app --reload --host 0.0.0.0 --port 8001

Then POST a recording (.wav/.m4a/.mp3) to /quality/check as multipart
form-data: field "audio" (the file) and field "task" ("vowel" or "ddk").

The response is the report.json content from pipeline.run_gate. A rejected
recording is NOT an HTTP error: it returns 200 with "decision": "FAIL" and a
"user_message" the app can show ("Please record again in a quieter room").
HTTP errors are only for bad requests (400) or unreadable audio (422).

GET /health also returns the gate's thresholds; GET /quality/plots/<clip_id>/waveform.png
(or spectrogram.png) returns the plot saved for a checked clip (the Live Mic Test screen shows them).
"""

import os
import re
import shutil
import tempfile

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from component1_robustness.config import load_config, resolve_path
from component1_robustness.pipeline import TASKS, run_gate
from component1_robustness.voice_check import voice_check_config

ALLOWED_EXTENSIONS = (".wav", ".m4a", ".mp3")
PLOT_FILES = ("waveform.png", "spectrogram.png")   # the only files /quality/plots serves
CLIP_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")    # clip ids are a safe stem + "_" + hash prefix

app = FastAPI(title="Component 1 - Audio Quality Gate API")

# Wide open for dev/demo (a phone on the same wifi hitting a laptop's IP
# has no fixed origin to allowlist). Tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_config() -> dict:
    """The fixed developer config. Tests replace this via app.dependency_overrides."""
    return load_config()


@app.get("/health")
def health(config: dict = Depends(get_config)):
    return {
        "status": "ok",
        "component": "quality_gate",
        "gate_model": config["gate_model"],
        "enhancement_method": config["enhancement_method"],
        "config_version": str(config["config_version"]),
        "thresholds": _thresholds(config),
    }


def _thresholds(config: dict) -> dict:
    """The limits the gate compares against, so a client can show them next to the measured values."""
    voice = voice_check_config(config)
    return {
        "min_duration_s": config["min_duration_s"],
        "max_duration_s": config["max_duration_s"],
        "max_clipping_pct": config["max_clipping_pct"],
        "min_voice_activity_pct": config["min_voice_activity_pct"],
        "comp1a_pass_db": config.get("comp1a_pass_db", 10.0),
        "min_speech_band_contrast_db": voice["min_speech_band_contrast_db"],
        "no_voice_max_level_dbfs": voice["no_voice_max_level_dbfs"],
        "feature_tolerances": {task: dict(config[key]) for task, key in (("vowel", "feature_tolerances"),
                                                                      ("ddk", "ddk_feature_tolerances"))},
    }


def _validate_extension(upload: UploadFile) -> str:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {ext!r}. Use one of {ALLOWED_EXTENSIONS}.",
        )
    return ext


def _validate_task(task: str) -> str:
    if task not in TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task {task!r}. Use one of {list(TASKS)}.")
    return task


def _safe_stem(filename: str | None) -> str:
    """Upload name without folders or odd characters (it becomes part of clip_id)."""
    stem = os.path.splitext(os.path.basename(filename or ""))[0]
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")
    return stem or "upload"


def _log_result(report: dict) -> None:
    print(
        f"[RESULT] {report['task']:<5} -> {report['decision']:<4} ({report['reason']})  "
        f"score={report['quality_score']:.1f}  audio={report['audio_choice']}  "
        f"gate={report['gate_model']}  clip={report['clip_id']}",
        flush=True,
    )


@app.post("/quality/check")
async def quality_check(
    audio: UploadFile = File(...),
    task: str = Form(...),
    config: dict = Depends(get_config),
):
    """Accepts one recording and its task; returns Component 1's report.

    "decision" PASS -> "audio_for_next_stage" is the file to send to
    "next_component". FAIL -> show "user_message" and ask for a new recording.
    """
    _validate_task(task)
    ext = _validate_extension(audio)

    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_path = os.path.join(tmp_dir, _safe_stem(audio.filename) + ext)
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)
        report = run_gate(tmp_path, task, config)
    except Exception as e:
        # e.g. a corrupt or non-audio file that ffmpeg/librosa cannot decode
        raise HTTPException(status_code=422, detail=f"Could not read the recording: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    _log_result(report)
    return report


@app.get("/quality/plots/{clip_id}/{name}")
def quality_plot(clip_id: str, name: str, config: dict = Depends(get_config)):
    """A plot run_gate saved for a checked clip: waveform.png or spectrogram.png (raw above enhanced).

    Only those two file names, and only clip ids made of letters, digits, "_" and "-",
    so nothing else in the outputs folder can be fetched.
    """
    if name not in PLOT_FILES or not CLIP_ID_PATTERN.match(clip_id):
        raise HTTPException(status_code=404, detail="Not found")
    path = resolve_path(config, "outputs") / clip_id / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="image/png")
