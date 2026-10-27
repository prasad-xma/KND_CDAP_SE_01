"""Biomarker-preservation check: did enhancement keep Component 2's features intact?

Component 1 uses Component 2's OWN feature extractor (never a copy of it), so
"preserved" means preserved for the model that will actually use the audio.
"""

import math
import os
import tempfile

import joblib
import numpy as np
import pandas as pd
import soundfile as sf

from component1_robustness.config import resolve_path
from component2_phonation.features import extract_phonation_features

EPS = 1e-12
NO_PREDICTION = -1   # Component 2 found no voiced frames


def phonation_features(y: np.ndarray, sr: int) -> dict[str, float] | None:
    """Component 2's 10 phonation features for an in-memory signal.

    Writes a temporary 32-bit float WAV (no quantisation loss), calls
    component2_phonation.features.extract_phonation_features, then deletes it.
    Returns None if Component 2 finds no voiced frames.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)  # Windows cannot reopen a file that is still open
    try:
        sf.write(tmp_path, np.asarray(y, dtype=np.float32), sr, subtype="FLOAT")
        return extract_phonation_features(tmp_path)
    finally:
        os.remove(tmp_path)


def relative_diff(before: float, after: float) -> float:
    """|after - before| / |before|. NaN if either value is NaN."""
    if math.isnan(before) or math.isnan(after):
        return math.nan
    return abs(after - before) / max(abs(before), EPS)


def compare_features(before: dict[str, float] | None, after: dict[str, float] | None,
                     tolerances: dict[str, float]) -> dict:
    """Check each feature in `tolerances` stayed within its relative tolerance.

    Returns {"per_feature": {name: relative_diff}, "preserved": bool}.
    Not preserved if either side has no features (no voiced frames), or any
    checked feature is missing, NaN, or moved more than its tolerance.
    """
    if before is None or after is None:
        return {"per_feature": {}, "preserved": False}

    per_feature = {}
    preserved = True
    for name, tolerance in tolerances.items():
        if name not in before or name not in after:
            per_feature[name] = math.nan
            preserved = False
            continue
        diff = relative_diff(float(before[name]), float(after[name]))
        per_feature[name] = diff
        if math.isnan(diff) or diff > tolerance:
            preserved = False
    return {"per_feature": per_feature, "preserved": preserved}


def load_component2_model(config: dict) -> tuple[object, list[str]]:
    """Component 2's model (config paths.component2_model) and the feature names it expects."""
    bundle = joblib.load(resolve_path(config, "component2_model"))
    return bundle["model"], bundle["feature_names"]


def predict_component2(model, feature_names: list[str], feats: dict | None) -> tuple[int, float]:
    """(prediction, P(PD)) from Component 2's model; (NO_PREDICTION, nan) if there are no features."""
    if feats is None:
        return NO_PREDICTION, math.nan
    X = pd.DataFrame([feats])[feature_names]
    return int(model.predict(X)[0]), float(model.predict_proba(X)[0][1])
