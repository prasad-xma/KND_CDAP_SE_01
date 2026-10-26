"""Run the saved Component 3 DDK model for inference-only predictions.

The default command predicts the two personal recordings:

    python -m component3_ddk.predict

Specific WAV files may be supplied instead:

    python -m component3_ddk.predict path/to/recording.wav

These outputs are experimental model predictions, not medical diagnoses.
"""

import argparse
from pathlib import Path

import joblib
import pandas as pd

from .features import FEATURE_NAMES, extract_ddk_features

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO_ROOT / "models" / "component3_ddk_ddk_rf.joblib"
PERSONAL_DDK_DIR = REPO_ROOT / "data" / "personal_ddk"
DEFAULT_AUDIO_PATHS = (
    PERSONAL_DDK_DIR / "DDK001-pa.wav",
    PERSONAL_DDK_DIR / "DDK001-ta.wav",
)


def _pd_class_index(classes):
    """Return the probability-column index for the PD class."""
    for index, class_value in enumerate(classes):
        normalized = str(class_value).strip().lower()
        if normalized == "pd" or class_value == 1:
            return index
    raise ValueError(
        "The saved model classes_ do not contain a recognizable PD class. "
        f"Found classes: {list(classes)!r}"
    )


def _class_name(class_value):
    normalized = str(class_value).strip().lower()
    if normalized == "pd" or class_value == 1:
        return "PD"
    if normalized == "hc" or class_value == 0:
        return "HC"
    return str(class_value)


def _task_name(audio_path):
    stem = audio_path.stem.lower()
    if stem.endswith("-pa"):
        return "D1/pa"
    if stem.endswith("-ta"):
        return "D2/ta"
    return "unknown"


def predict(audio_path, model_path=MODEL_PATH):
    """Predict one recording without fitting or modifying any artifacts."""
    model_path = Path(model_path)
    if not model_path.is_file():
        raise FileNotFoundError(f"Model bundle not found: {model_path}")

    bundle = joblib.load(model_path)
    if "model" not in bundle or "feature_names" not in bundle:
        raise KeyError("Model bundle must contain 'model' and 'feature_names'.")

    model = bundle["model"]
    feature_names = list(bundle["feature_names"])
    if feature_names != list(FEATURE_NAMES):
        raise ValueError(
            "Saved model feature order does not match component3_ddk.features.FEATURE_NAMES."
        )
    if not hasattr(model, "classes_"):
        raise AttributeError("Saved model does not expose classes_.")

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Recording not found: {audio_path}")

    features = extract_ddk_features(str(audio_path))
    if features is None:
        raise ValueError(f"Too few syllable onsets detected in {audio_path}")

    X = pd.DataFrame([{name: features[name] for name in feature_names}], columns=feature_names)
    prediction_value = model.predict(X)[0]
    probabilities = model.predict_proba(X)[0]
    pd_index = _pd_class_index(model.classes_)

    return {
        "filename": audio_path.name,
        "task": _task_name(audio_path),
        "predicted_class": _class_name(prediction_value),
        "pd_probability": float(probabilities[pd_index]),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run inference-only Component 3 DDK predictions."
    )
    parser.add_argument(
        "audio_paths",
        nargs="*",
        type=Path,
        help="WAV recordings; defaults to the two files in data/personal_ddk.",
    )
    args = parser.parse_args()
    audio_paths = tuple(args.audio_paths) or DEFAULT_AUDIO_PATHS

    results = [predict(path) for path in audio_paths]
    print("Experimental model outputs only; not a medical diagnosis.")
    for result in results:
        print(
            f"{result['filename']} | task={result['task']} | "
            f"prediction={result['predicted_class']} | "
            f"PD probability={result['pd_probability']:.4f}"
        )
    if len(results) > 1:
        mean_probability = sum(item["pd_probability"] for item in results) / len(results)
        print(
            f"Mean available PD probability across {len(results)} recordings: "
            f"{mean_probability:.4f} (descriptive summary only)"
        )


if __name__ == "__main__":
    main()
