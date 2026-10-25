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
"""

import os
import re
import shutil
import tempfile

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from component1_robustness.config import load_config, resolve_path
from component1_robustness.dnsmos import is_available as dnsmos_available
from component1_robustness.pipeline import TASKS, run_gate

ALLOWED_EXTENSIONS = (".wav", ".m4a", ".mp3")

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
        "dnsmos_available": dnsmos_available(resolve_path(config, "dnsmos_model")),
        "config_version": str(config["config_version"]),
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
