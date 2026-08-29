"""Run a trained Component 2 phonation model on a single .wav file.

Usage:
    python -m src.component2_phonation.predict path/to/recording.wav [readtext|vowel]
"""

import os
import sys

import joblib
import pandas as pd

from .features import extract_phonation_features

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS_DIR = os.path.join(REPO_ROOT, "models")


def model_path_for(task="readtext"):
    return os.path.join(MODELS_DIR, f"component2_phonation_{task}_rf.joblib")


def predict(audio_path, model_path=None, task="readtext"):
    model_path = model_path or model_path_for(task)
    bundle = joblib.load(model_path)
    model = bundle["model"]
    feature_names = bundle["feature_names"]

    features = extract_phonation_features(audio_path)
    if features is None:
        raise ValueError(f"No voiced frames detected in {audio_path}")

    X = pd.DataFrame([features])[feature_names]
    prediction = int(model.predict(X)[0])
    probability = model.predict_proba(X)[0]

    return {
        "audio_path": audio_path,
        "model_path": model_path,
        "prediction": "PD" if prediction == 1 else "HC",
        "probability_hc": float(probability[0]),
        "probability_pd": float(probability[1]),
        "features": features,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.component2_phonation.predict <audio_path> [readtext|vowel]")
        sys.exit(1)

    audio_arg = sys.argv[1]
    task_arg = sys.argv[2] if len(sys.argv) > 2 else "readtext"

    result = predict(audio_arg, task=task_arg)
    print(f"Model: {result['model_path']}")
    print(f"Audio: {result['audio_path']}")
    print(f"Prediction: {result['prediction']}")
    print(f"P(HC) = {result['probability_hc']:.4f}   P(PD) = {result['probability_pd']:.4f}")
