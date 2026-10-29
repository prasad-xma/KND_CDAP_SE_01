"""Quality-gate models compared in the Component 1 benchmark.

Shared interface (every model):
    fit(X, y, groups=None)  X: DataFrame, one row per clip = a gate_inputs() dict
                            y: "reliable"/"unreliable" (or 1/0)
    predict(quality)        quality: one gate_inputs() dict
        -> {"decision": "PASS"|"FAIL", "quality_score": 0-100, "reason": str}

Every model first applies the same hard rules, in this order:
    duration outside [min_duration_s, max_duration_s] -> FAIL "too_short"/"too_long"
    clipping_pct > max_clipping_pct                    -> FAIL "clipped"
    voice_activity_pct < min_voice_activity_pct        -> FAIL "no_voice"
Only then does the model itself decide.

Models:
    comp1-A          rule: speech-band contrast >= comp1a_pass_db (10 dB). Until config v1.4
                     it was SNR/HNR >= reliable_db; HNR could not separate a real voice from
                     steady room hum on a laptop mic (see quality_metrics.speech_band_contrast_db).
    comp1-B-rf/svm/logreg   classical ML on quality metrics + MFCC means
"""

from pathlib import Path

import joblib
import librosa
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from component1_robustness.config import resolve_path
from component1_robustness.quality_metrics import MAX_SNR_DB, compute_quality, duration_reason

PASS, FAIL = "PASS", "FAIL"
RELIABLE = "reliable"
B_CLASSIFIERS = ("rf", "svm", "logreg")
GATE_NAMES = ("comp1-A", *(f"comp1-B-{c}" for c in B_CLASSIFIERS))
TRAINABLE = tuple(n for n in GATE_NAMES if n != "comp1-A")


# --- Inputs shared by all gates -------------------------------------------------

def mfcc_means(y: np.ndarray, sr: int, n_mfcc: int) -> dict[str, float]:
    """Mean of each MFCC over time: a compact summary of the spectral shape."""
    mfcc = librosa.feature.mfcc(y=np.asarray(y, dtype=np.float32), sr=sr, n_mfcc=n_mfcc)
    return {f"mfcc_mean_{i + 1}": float(v) for i, v in enumerate(mfcc.mean(axis=1))}


def gate_inputs(y: np.ndarray, sr: int, config: dict) -> dict:
    """Everything any gate needs for one clip: compute_quality() + MFCC means.

    MFCCs are taken after resampling to config["sample_rate"] so clips recorded
    at different rates are described on the same frequency scale.
    """
    inputs = compute_quality(y, sr)
    target_sr = config["sample_rate"]
    y_std = librosa.resample(np.asarray(y, dtype=np.float32), orig_sr=sr, target_sr=target_sr) \
        if sr != target_sr else y
    inputs.update(mfcc_means(y_std, target_sr, config["n_mfcc"]))
    return inputs


# --- Base class: shared hard rules ------------------------------------------------

def _result(decision: str, score: float, reason: str) -> dict:
    return {"decision": decision, "quality_score": float(np.clip(score, 0.0, 100.0)), "reason": reason}


class GateModel:
    """Base class. Subclasses implement _decide(quality) and, if trainable, fit()."""

    name = "base"

    def __init__(self, config: dict):
        self.config = config

    def fit(self, X: pd.DataFrame, y, groups=None) -> "GateModel":
        """Rule-based models have nothing to learn; trainable models override this."""
        return self

    def _precheck(self, quality: dict) -> dict | None:
        """The hard rules every model applies first. Returns a FAIL result or None."""
        c = self.config
        reason = duration_reason(quality["duration_s"], c["min_duration_s"], c["max_duration_s"])
        if reason != "ok":
            return _result(FAIL, 0.0, reason)
        if quality["clipping_pct"] > c["max_clipping_pct"]:
            return _result(FAIL, 0.0, "clipped")
        if quality["voice_activity_pct"] < c["min_voice_activity_pct"]:
            return _result(FAIL, 0.0, "no_voice")
        return None

    def predict(self, quality: dict) -> dict:
        return self._precheck(quality) or self._decide(quality)

    def _decide(self, quality: dict) -> dict:
        raise NotImplementedError


# --- comp1-A: the existing rule -----------------------------------------------------

class Comp1A_RuleBased(GateModel):
    """PASS if the speech-band contrast >= comp1a_pass_db (default 10 dB).

    Until config v1.4 this rule used the SNR/HNR estimate against reliable_db (removed in v1.5).
    """

    name = "comp1-A"

    def score(self, estimate_db: float) -> float:
        """Linear map: pass threshold -> 50, threshold +/- span -> 100 / 0 (clipped)."""
        span = self.config["comp1a_score_span_db"]
        return float(np.clip(50.0 + 50.0 * (estimate_db - self._pass_db()) / span, 0.0, 100.0))

    def _pass_db(self) -> float:
        return float(self.config.get("comp1a_pass_db", 10.0))

    def _decide(self, quality: dict) -> dict:
        estimate = quality["speech_band_contrast_db"]
        passed = estimate >= self._pass_db()
        return _result(PASS if passed else FAIL, self.score(estimate), "ok" if passed else "low_snr")


# --- Trainable models: shared fit / predict on a feature table --------------------

def _to_binary(y) -> np.ndarray:
    """'reliable'/True/1 -> 1, anything else -> 0."""
    return np.array([1 if (v == RELIABLE or v is True or v == 1) else 0 for v in y])


class _TrainableGate(GateModel):
    """A sklearn classifier on fixed feature columns; score = P(reliable) x 100."""

    def feature_columns(self) -> list[str]:
        raise NotImplementedError

    def _make_classifier(self):
        raise NotImplementedError

    def _matrix(self, rows: pd.DataFrame) -> np.ndarray:
        """Feature matrix with the derived columns; +/-inf SNR clipped to +/-MAX_SNR_DB."""
        rows = rows.copy()
        if "estimated_snr_db" in rows:
            rows["estimated_snr_db"] = rows["estimated_snr_db"].clip(-MAX_SNR_DB, MAX_SNR_DB)
        if "method" in rows:
            rows["method_is_hnr"] = (rows["method"] == "hnr").astype(float)
        return rows[self.feature_columns()].to_numpy(dtype=float)

    def fit(self, X: pd.DataFrame, y, groups=None) -> "_TrainableGate":
        """Train on all rows. groups is accepted for the shared interface (used by CV, not here)."""
        self.classifier = self._make_classifier()
        self.classifier.fit(self._matrix(pd.DataFrame(X)), _to_binary(y))
        return self

    def probability_reliable(self, quality: dict) -> float:
        if not hasattr(self, "classifier"):
            raise RuntimeError(f"{self.name} must be fitted (or loaded) before predict()")
        proba = self.classifier.predict_proba(self._matrix(pd.DataFrame([quality])))[0]
        classes = list(self.classifier.classes_)
        return float(proba[classes.index(1)]) if 1 in classes else 0.0

    def _decide(self, quality: dict) -> dict:
        p = self.probability_reliable(quality)
        passed = p >= self.config["gate_pass_probability"]
        return _result(PASS if passed else FAIL, 100.0 * p, "ok" if passed else "low_quality")


# --- comp1-B: classical ML ----------------------------------------------------------

B_BASE_FEATURES = ["level_dbfs", "clipping_pct", "voice_activity_pct", "estimated_snr_db", "method_is_hnr"]


class Comp1B_ClassicalML(_TrainableGate):
    """RF / SVM / LogReg (as in common/model_evaluation.py) on quality metrics + MFCC means."""

    def __init__(self, config: dict, classifier: str = "rf"):
        if classifier not in B_CLASSIFIERS:
            raise ValueError(f"classifier must be one of {B_CLASSIFIERS}")
        super().__init__(config)
        self.classifier_name = classifier
        self.name = f"comp1-B-{classifier}"

    def feature_columns(self) -> list[str]:
        return B_BASE_FEATURES + [f"mfcc_mean_{i + 1}" for i in range(self.config["n_mfcc"])]

    def _make_classifier(self):
        seed = self.config["seed"]
        if self.classifier_name == "rf":
            model = RandomForestClassifier(n_estimators=200, random_state=seed, class_weight="balanced")
        elif self.classifier_name == "svm":
            model = SVC(kernel="rbf", class_weight="balanced", probability=True, random_state=seed)
        else:
            model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed)
        return Pipeline([("scaler", StandardScaler()), ("clf", model)])


# --- Factory, save / load -------------------------------------------

def get_gate_model(name: str, config: dict) -> GateModel:
    """New (untrained) gate model by name. Raises ValueError for an unknown name."""
    if name == "comp1-A":
        return Comp1A_RuleBased(config)
    if name.startswith("comp1-B-"):
        return Comp1B_ClassicalML(config, classifier=name.removeprefix("comp1-B-"))
    raise ValueError(f"Unknown gate model {name!r}; choose from {GATE_NAMES}")


def gate_model_path(name: str, config: dict) -> Path:
    return resolve_path(config, "models") / f"component1_gate_{name}.joblib"


def save_gate_model(model: GateModel, config: dict) -> Path:
    """Save a trained comp1-B model to models/component1_gate_<name>.joblib."""
    if model.name not in TRAINABLE:
        raise ValueError(f"{model.name} is rule-based; there is nothing to save")
    path = gate_model_path(model.name, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


def load_gate_model(name: str, config: dict) -> GateModel:
    """comp1-A is built from config; trained models are loaded from their .joblib file."""
    if name not in TRAINABLE:
        return get_gate_model(name, config)
    model = joblib.load(gate_model_path(name, config))
    model.config = config
    return model
