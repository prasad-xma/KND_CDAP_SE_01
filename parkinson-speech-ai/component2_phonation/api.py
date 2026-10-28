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
from typing import List

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


def _validate_extension(upload: UploadFile) -> str:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {ext!r}. Use one of {ALLOWED_EXTENSIONS}.",
        )
    return ext


def _log_result(label: str, response: dict) -> None:
    f = response["features"]
    print(
        f"[RESULT] {label:<11}-> {response['prediction']:>2}  "
        f"P(PD)={response['probability_pd']:.3f}  "
        f"model={response['model_used']:<19}  "
        f"F0={f['mean_f0']:.1f}Hz  jitter={f['jitter'] * 100:.2f}%  "
        f"shimmer={f['shimmer'] * 100:.2f}%  HNR={f['hnr']:.1f}dB",
        flush=True,
    )


async def _score_recording(audio: UploadFile, extract_vowel_segment: bool) -> dict:
    ext = _validate_extension(audio)

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
    response = await _score_recording(audio, extract_vowel_segment)
    _log_result("SINGLE", response)
    return response


@app.post("/phonation/screen_vowel_multi")
async def screen_vowel_multi(audio_files: List[UploadFile] = File(...)):
    """Accepts N sustained-vowel recordings of the same person, scores each
    independently with the vowel model, and averages the PD probabilities -
    reduces take-to-take measurement noise (duration, breath support,
    environment) compared to relying on a single recording.
    """
    if len(audio_files) < 1:
        raise HTTPException(status_code=400, detail="At least one recording is required.")

    recordings = []
    for audio in audio_files:
        r = await _score_recording(audio, extract_vowel_segment=True)
        recordings.append(r)

    avg_probability_pd = sum(r["probability_pd"] for r in recordings) / len(recordings)
    avg_probability_hc = 1 - avg_probability_pd
    avg_prediction = "PD" if avg_probability_pd >= 0.5 else "HC"

    for i, r in enumerate(recordings):
        _log_result(f"VOWEL_{i + 1}", r)
    print(
        f"[RESULT] VOWEL_AVG  -> {avg_prediction:>2}  "
        f"P(PD)={avg_probability_pd:.3f}  P(HC)={avg_probability_hc:.3f}  "
        f"(n={len(recordings)})",
        flush=True,
    )

    return {
        "prediction": avg_prediction,
        "probability_pd": avg_probability_pd,
        "probability_hc": avg_probability_hc,
        "recordings": recordings,
    }


@app.post("/phonation/screen_dual")
async def screen_phonation_dual(
    vowel_audio: UploadFile = File(...),
    phrase_audio: UploadFile = File(...),
):
    vowel_result = await _score_recording(vowel_audio, extract_vowel_segment=True)
    phrase_result = await _score_recording(phrase_audio, extract_vowel_segment=False)

    fused_probability_pd = (vowel_result["probability_pd"] + phrase_result["probability_pd"]) / 2
    fused_probability_hc = 1 - fused_probability_pd
    fused_prediction = "PD" if fused_probability_pd >= 0.5 else "HC"

    _log_result("VOWEL", vowel_result)
    _log_result("PHRASE", phrase_result)
    print(
        f"[RESULT] FUSED      -> {fused_prediction:>2}  "
        f"P(PD)={fused_probability_pd:.3f}  P(HC)={fused_probability_hc:.3f}",
        flush=True,
    )

    return {
        "prediction": fused_prediction,
        "probability_pd": fused_probability_pd,
        "probability_hc": fused_probability_hc,
        "vowel_task": vowel_result,
        "phrase_task": phrase_result,
    }
