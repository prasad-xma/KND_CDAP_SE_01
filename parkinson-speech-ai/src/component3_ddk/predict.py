"""Run the trained Component 3 DDK model on a single "pa"/"ta" recording.

Usage:
    python -m src.component3_ddk.predict path/to/recording.wav
"""

import os
import sys

import joblib
import pandas as pd

from .features import extract_ddk_features

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL_PATH = os.path.join(REPO_ROOT, "models", "component3_ddk_ddk_rf.joblib")


def predict(audio_path, model_path=MODEL_PATH):
    bundle = joblib.load(model_path)
    model = bundle["model"]
    feature_names = bundle["feature_names"]

    features = extract_ddk_features(audio_path)
    if features is None:
        raise ValueError(f"Too few syllable onsets detected in {audio_path}")

    X = pd.DataFrame([features])[feature_names]
    prediction = int(model.predict(X)[0])
    probability = model.predict_proba(X)[0]

    return {
        "audio_path": audio_path,
        "prediction": "PD" if prediction == 1 else "HC",
        "probability_hc": float(probability[0]),
        "probability_pd": float(probability[1]),
        "features": features,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m src.component3_ddk.predict <audio_path>")
        sys.exit(1)

    result = predict(sys.argv[1])
    print(f"Audio: {result['audio_path']}")
    print(f"Prediction: {result['prediction']}")
    print(f"P(HC) = {result['probability_hc']:.4f}   P(PD) = {result['probability_pd']:.4f}")
