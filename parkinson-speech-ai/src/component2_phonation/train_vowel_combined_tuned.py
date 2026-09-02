"""Feature-selected, hyperparameter-tuned version of Component 2's best
baseline (combined AH + Italian PVS sustained-vowel data).

Same technique already used for the Sakar baseline (`train_sakar_tuned.py`):
SelectKBest + RF / SVM / HistGradientBoosting with class-imbalance handling,
searched via RandomizedSearchCV under the same participant-grouped CV
protocol (no leakage across a participant's recordings). Reports whatever
comes out — this is a legitimate search over models/features, not a target
to hit a specific number.

Usage:
    python -m src.component2_phonation.train_vowel_combined_tuned
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

from .train_vowel_combined import _load_ah, _load_italian
from .features import FEATURE_NAMES
from ..common.model_evaluation import REPO_ROOT, MODELS_DIR, RANDOM_STATE

RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component2_phonation")
N_SPLITS = 5


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    ah_df = _load_ah()
    ah_df["source"] = "AH_dataset"
    ah_df["participant_id"] = "AH_" + ah_df["participant_id"].astype(str)
    italian_df = _load_italian()
    italian_df["source"] = "Italian_PVS"
    df = pd.concat([ah_df, italian_df], ignore_index=True)

    X = df[FEATURE_NAMES].values
    y = df["label"].values
    groups = df["participant_id"].values

    print(f"Total recordings: {len(df)}, participants: {df['participant_id'].nunique()}")
    print(f"PD: {sum(y == 1)}  HC: {sum(y == 0)}")

    cv = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("select", SelectKBest(f_classif)),
        ("clf", SVC(kernel="rbf", class_weight="balanced", random_state=RANDOM_STATE)),
    ])

    k_options = [3, 5, 7, 10, len(FEATURE_NAMES)]  # only 10 features total here, unlike Sakar's 752

    param_distributions = [
        {
            "select__k": k_options,
            "clf": [SVC(kernel="rbf", class_weight="balanced", random_state=RANDOM_STATE)],
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
    model_path = os.path.join(MODELS_DIR, "component2_phonation_vowel_combined_tuned.joblib")
    joblib.dump({"model": best_model, "feature_names": FEATURE_NAMES}, model_path)
    print(f"\nSaved tuned model to {model_path}")

    metrics = {
        "best_params": {k: str(v) for k, v in search.best_params_.items()},
        "cv_accuracy": float(acc),
        "cv_balanced_accuracy": float(bal_acc),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
    }
    metrics_path = os.path.join(RESULTS_DIR, "vowel_combined_tuned_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
