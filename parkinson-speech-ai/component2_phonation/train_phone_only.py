"""
Usage:
    python -m component2_phonation.train_phone_only
"""

import os
import json

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.model_selection import StratifiedGroupKFold, RandomizedSearchCV, cross_val_predict
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
)

from .train_vowel_combined import _load_phone_recorded_pd, _load_phone_recorded_healthy
from .phone_recorded_healthy_italian_dataset import build_phone_recorded_healthy_italian_features
from .phone_recorded_pd_italian_dataset import build_phone_recorded_pd_italian_features
from .phone_recorded_local_healthy_training_dataset import build_phone_recorded_local_healthy_training_features
from .features import FEATURE_NAMES
from common.model_evaluation import REPO_ROOT, MODELS_DIR, RANDOM_STATE

RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component2_phonation")
PHONE_RECORDED_HEALTHY_ITALIAN_FEATURES_CSV = os.path.join(
    RESULTS_DIR, "phone_recorded_healthy_italian_features.csv"
)
PHONE_RECORDED_PD_ITALIAN_FEATURES_CSV = os.path.join(
    RESULTS_DIR, "phone_recorded_pd_italian_features.csv"
)
PHONE_RECORDED_LOCAL_HEALTHY_TRAINING_FEATURES_CSV = os.path.join(
    RESULTS_DIR, "phone_recorded_local_healthy_training_features.csv"
)
N_SPLITS = 5
INCLUDE_PD_ITALIAN = False
INCLUDE_HEALTHY_ITALIAN = True
INCLUDE_LOCAL_HEALTHY_TRAINING = True


def _load_phone_recorded_healthy_italian():
    if os.path.exists(PHONE_RECORDED_HEALTHY_ITALIAN_FEATURES_CSV):
        print(f"Loading cached phone-recorded-healthy-italian features from {PHONE_RECORDED_HEALTHY_ITALIAN_FEATURES_CSV}")
        return pd.read_csv(PHONE_RECORDED_HEALTHY_ITALIAN_FEATURES_CSV)
    df = build_phone_recorded_healthy_italian_features()
    df.to_csv(PHONE_RECORDED_HEALTHY_ITALIAN_FEATURES_CSV, index=False)
    return df


def _load_phone_recorded_pd_italian():
    if os.path.exists(PHONE_RECORDED_PD_ITALIAN_FEATURES_CSV):
        print(f"Loading cached phone-recorded-pd-italian features from {PHONE_RECORDED_PD_ITALIAN_FEATURES_CSV}")
        return pd.read_csv(PHONE_RECORDED_PD_ITALIAN_FEATURES_CSV)
    df = build_phone_recorded_pd_italian_features()
    df.to_csv(PHONE_RECORDED_PD_ITALIAN_FEATURES_CSV, index=False)
    return df


def _load_phone_recorded_local_healthy_training():
    if os.path.exists(PHONE_RECORDED_LOCAL_HEALTHY_TRAINING_FEATURES_CSV):
        print(f"Loading cached local-healthy-training features from {PHONE_RECORDED_LOCAL_HEALTHY_TRAINING_FEATURES_CSV}")
        return pd.read_csv(PHONE_RECORDED_LOCAL_HEALTHY_TRAINING_FEATURES_CSV)
    df = build_phone_recorded_local_healthy_training_features()
    df.to_csv(PHONE_RECORDED_LOCAL_HEALTHY_TRAINING_FEATURES_CSV, index=False)
    return df


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    phone_pd_df = _load_phone_recorded_pd()
    phone_pd_df["source"] = "Phone_Recorded_PD"
    phone_healthy_df = _load_phone_recorded_healthy()
    phone_healthy_df["source"] = "Phone_Recorded_Healthy"

    frames = [phone_pd_df, phone_healthy_df]

    if INCLUDE_PD_ITALIAN:
        phone_pd_italian_df = _load_phone_recorded_pd_italian()
        phone_pd_italian_df["source"] = "Phone_Recorded_PD_Italian"
        frames.append(phone_pd_italian_df)

    if INCLUDE_HEALTHY_ITALIAN:
        phone_healthy_italian_df = _load_phone_recorded_healthy_italian()
        phone_healthy_italian_df["source"] = "Phone_Recorded_Healthy_Italian"
        frames.append(phone_healthy_italian_df)

    if INCLUDE_LOCAL_HEALTHY_TRAINING:
        local_healthy_training_df = _load_phone_recorded_local_healthy_training()
        local_healthy_training_df["source"] = "Local_Healthy_Training"
        frames.append(local_healthy_training_df)

    df = pd.concat(frames, ignore_index=True)

    X = df[FEATURE_NAMES].values
    y = df["label"].values
    groups = df["participant_id"].values

    print(f"Total recordings: {len(df)}, participants: {df['participant_id'].nunique()}")
    print(f"PD: {sum(y == 1)}  HC: {sum(y == 0)}")

    cv = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("select", SelectKBest(f_classif)),
        ("clf", SVC(kernel="rbf", class_weight="balanced", random_state=RANDOM_STATE, probability=True)),
    ])

    k_options = [3, 5, 7, 10, len(FEATURE_NAMES)]

    param_distributions = [
        {
            "select__k": k_options,
            "clf": [SVC(kernel="rbf", class_weight="balanced", random_state=RANDOM_STATE, probability=True)],
            "clf__C": [0.1, 1, 10, 50, 100],
            "clf__gamma": ["scale", "auto", 0.001, 0.01],
        },
        {
            "select__k": k_options,
            "clf": [RandomForestClassifier(class_weight="balanced", random_state=RANDOM_STATE)],
            "clf__n_estimators": [200, 500],
            "clf__max_depth": [None, 5, 10, 20],
        },
        {
            "select__k": k_options,
            "clf": [HistGradientBoostingClassifier(class_weight="balanced", random_state=RANDOM_STATE)],
            "clf__max_iter": [100, 200],
            "clf__learning_rate": [0.05, 0.1, 0.2],
        },
    ]

    search = RandomizedSearchCV(
        pipe,
        param_distributions=param_distributions,
        n_iter=30,
        scoring="balanced_accuracy",
        cv=cv,
        random_state=RANDOM_STATE,
        n_jobs=1,
        verbose=1,
    )
    search.fit(X, y, groups=groups)

    print("\nBest params:", search.best_params_)
    print("Best CV balanced accuracy (from search):", round(search.best_score_, 4))

    best_model = search.best_estimator_
    y_pred_cv = cross_val_predict(best_model, X, y, groups=groups, cv=cv)

    acc = accuracy_score(y, y_pred_cv)
    bal_acc = balanced_accuracy_score(y, y_pred_cv)
    report = classification_report(y, y_pred_cv, target_names=["HC", "PD"], digits=4, output_dict=True)
    cm = confusion_matrix(y, y_pred_cv)

    print(f"\nCV accuracy: {acc:.4f}   CV balanced accuracy: {bal_acc:.4f}")
    print(classification_report(y, y_pred_cv, target_names=["HC", "PD"], digits=4))
    print("Confusion matrix:\n", cm)

    best_model.fit(X, y)
    model_path = os.path.join(MODELS_DIR, "component2_phonation_phone_only.joblib")
    joblib.dump({"model": best_model, "feature_names": FEATURE_NAMES}, model_path)
    print(f"\nSaved phone-only model to {model_path}")

    metrics = {
        "note": "Trained ONLY on phone_recorded_PD + phone_recorded_Healthy (81 recordings, "
                "all captured via phone mic re-recording of PD_AH/HC_AH playback). "
                "No AH/Italian/Kaggle/local_healthy data included.",
        "best_params": {k: str(v) for k, v in search.best_params_.items()},
        "cv_accuracy": float(acc),
        "cv_balanced_accuracy": float(bal_acc),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
    }
    metrics_path = os.path.join(RESULTS_DIR, "phone_only_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
