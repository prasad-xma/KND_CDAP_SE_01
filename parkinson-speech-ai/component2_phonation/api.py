"""Standalone HTTP server for Component 2 (phonation), independent of
Components 1/3 so it can be built and demoed on its own.

Wraps `predict.predict()` using the best real result this component has
(the vowel-combined tuned model, 82.7% CV accuracy / 82.8% balanced
accuracy on 126 participants) behind one endpoint, so the Flutter app's
`features/phonation/` screen has something to call.

Run from `parkinson-speech-ai/`:
    uvicorn component2_phonation.api:app --reload --host 0.0.0.0 --port 8000

Then POST a sustained-vowel recording (.wav/.m4a/.mp3) to /phonation/screen
as multipart form-data under the field name "audio".
"""

import os
import shutil
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .predict import REPO_ROOT, predict
from .vowel_segmentation import extract_longest_vowel_clip

VOWEL_MODEL_PATH = os.path.join(
    REPO_ROOT, "models", "component2_phonation_vowel_combined_tuned.joblib"
)
READTEXT_MODEL_PATH = os.path.join(
    REPO_ROOT, "models", "component2_phonation_readtext_rf.joblib"
)
# Kept for backwards compatibility with the /health check below.
MODEL_PATH = VOWEL_MODEL_PATH
ALLOWED_EXTENSIONS = (".wav", ".m4a", ".mp3")

app = FastAPI(title="Component 2 - Phonation Screening API")

# Wide open for dev/demo (a phone on the same wifi hitting a laptop's IP
# has no fixed origin to allowlist). Tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "component": "phonation",
        "model": os.path.basename(MODEL_PATH),
        "model_found": os.path.isfile(MODEL_PATH),
    }


@app.post("/phonation/screen")
async def screen_phonation(
    audio: UploadFile = File(...),
    extract_vowel_segment: bool = Form(False),
):
    """Accepts one recording, returns a PD/HC prediction + raw phonation
    features from Component 2's own model.

    `extract_vowel_segment` controls HOW the recording is measured, AND
    which trained model is applied - each setting uses the model that
    actually matches what it's being fed, so the prediction is meaningful
    either way (applying the vowel model to a whole untrimmed phrase
    recording would be testing it outside what it was ever trained on):
      - True: the longest vowel-like segment is cropped out first (see
        vowel_segmentation.py) and only that is measured - the cropped clip
        resembles a sustained-vowel recording, so the vowel-combined-tuned
        model (82.7% CV accuracy) is used.
      - False (default): the whole recording is measured as-is. This is
        the ReadText baseline's own approach, so the readtext-trained model
        (~78% CV accuracy, trained on MDVR-KCL English passage recordings)
        is used instead of the vowel model.
    """
    ext = os.path.splitext(audio.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {ext!r}. Use one of {ALLOWED_EXTENSIONS}.",
        )

    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    clip_path = None
    segment_info = None
    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)

        predict_path = tmp_path
        if extract_vowel_segment:
            segment = extract_longest_vowel_clip(tmp_path)
            if segment is None:
                raise HTTPException(
                    status_code=422,
                    detail="No sustained vowel-like segment (>=150ms continuous voicing) found.",
                )
            clip_path, start, end, duration = segment
            predict_path = clip_path
            segment_info = {
                "segment_start_seconds": round(start, 3),
                "segment_end_seconds": round(end, 3),
                "segment_duration_seconds": round(duration, 3),
            }

        model_path = VOWEL_MODEL_PATH if extract_vowel_segment else READTEXT_MODEL_PATH
        result = predict(predict_path, model_path=model_path)
    except ValueError as e:
        # e.g. "No voiced frames detected" - a genuinely bad/silent recording
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        os.remove(tmp_path)
        if clip_path and os.path.exists(clip_path):
            os.remove(clip_path)

    response = {
        "prediction": result["prediction"],
        "probability_pd": result["probability_pd"],
        "probability_hc": result["probability_hc"],
        "features": result["features"],
        "extraction_used": extract_vowel_segment,
        "model_used": "vowel_combined_tuned" if extract_vowel_segment else "readtext",
    }
    if segment_info:
        response.update(segment_info)
    return response
