"""FastAPI inference API for Component 3 DDK recordings.

Run from parkinson-speech-ai:
    uvicorn component3_ddk.api:app --reload --host 0.0.0.0 --port 8001
"""

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from .predict import MODEL_PATH, predict

app = FastAPI(title="Component 3 - DDK Speech-Motor API")
ALLOWED_EXTENSIONS = {".wav", ".m4a", ".mp3"}


def _extension(upload: UploadFile) -> str:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {extension!r}. Use WAV, M4A, or MP3.",
        )
    return extension


async def _score_upload(upload: UploadFile) -> dict:
    extension = _extension(upload)
    fd, temporary_path = tempfile.mkstemp(suffix=extension)
    os.close(fd)
    try:
        with open(temporary_path, "wb") as target:
            shutil.copyfileobj(upload.file, target)
        result = predict(temporary_path, model_path=MODEL_PATH)
        result["filename"] = upload.filename or result["filename"]
        return result
    except (OSError, ValueError, KeyError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "component": "ddk",
        "model": MODEL_PATH.name,
        "model_found": MODEL_PATH.is_file(),
    }


@app.post("/ddk/screen_dual")
async def screen_dual(
    pa_audio: UploadFile = File(...),
    ta_audio: UploadFile = File(...),
):
    pa_result = await _score_upload(pa_audio)
    ta_result = await _score_upload(ta_audio)
    mean_probability = (
        pa_result["pd_probability"] + ta_result["pd_probability"]
    ) / 2
    return {
        "pa_result": pa_result,
        "ta_result": ta_result,
        "mean_pd_probability": mean_probability,
        "combined_prediction": "PD" if mean_probability >= 0.5 else "HC",
        "interpretation_note": (
            "Experimental model output; not a medical diagnosis. "
            "The mean is descriptive and is not a validated participant-level score."
        ),
    }
