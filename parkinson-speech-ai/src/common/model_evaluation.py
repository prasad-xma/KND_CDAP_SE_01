"""Shared cross-validation training/evaluation logic, used across all components.

Keeping the CV protocol, model choice, and saved-artifact format identical
across components (and across baselines within a component) makes results
directly comparable and avoids re-implementing the same evaluation code
per-component.
"""

import os
import json

import joblib
import matplotlib.pyplot as plt
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS_DIR = os.path.join(REPO_ROOT, "models")

N_SPLITS = 5
RANDOM_STATE = 42


def run_baseline(df, name, prefix, results_dir, feature_names, model_prefix, component_label, n_splits=N_SPLITS):
    """Run participant-grouped CV for RF/SVM/LogReg, save the final RF model + plots + metrics.

    `df` must have columns: participant_id, label, label_name, plus each of feature_names.
    `name` identifies the task for the saved model filename (e.g. "readtext", "ddk").
    `prefix` is prepended to result filenames (e.g. "readtext_", "ddk_").
    `model_prefix` names the saved model file: "{model_prefix}_{name}_rf.joblib".
    `component_label` is used in plot titles (e.g. "Component 2", "Component 3").
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    X = df[feature_names]
    y = df["label"]
    groups = df["participant_id"]

    n_splits = min(n_splits, y.value_counts().min())
    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)

    candidates = {
        "random_forest": RandomForestClassifier(
            n_estimators=200, random_state=RANDOM_STATE, class_weight="balanced"
        ),
        "svm_rbf": Pipeline([
            ("scaler", StandardScaler()),
            ("svm", SVC(kernel="rbf", class_weight="balanced", random_state=RANDOM_STATE)),
        ]),
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("logistic", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)),
        ]),
    }

    cv_summary = {}
    for cname, model in candidates.items():
        scores = cross_val_score(model, X, y, groups=groups, cv=cv, scoring="accuracy")
        cv_summary[cname] = {
            "fold_accuracies": scores.tolist(),
            "mean": float(scores.mean()),
            "std": float(scores.std()),
        }
        print(f"{cname}: mean CV accuracy = {scores.mean():.4f} (+/- {scores.std():.4f})")

    rf = candidates["random_forest"]
    y_pred_cv = cross_val_predict(rf, X, y, groups=groups, cv=cv)

    accuracy = accuracy_score(y, y_pred_cv)
    report = classification_report(y, y_pred_cv, target_names=["HC", "PD"], digits=4, output_dict=True)
    cm = confusion_matrix(y, y_pred_cv)

    print(f"\nRandom Forest cross-validated accuracy: {accuracy:.4f}")
    print(classification_report(y, y_pred_cv, target_names=["HC", "PD"], digits=4))

    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["HC", "PD"])
    disp.plot()
    plt.title(f"{component_label} - {name} baseline (Random Forest, CV predictions)")
    plt.savefig(os.path.join(results_dir, f"{prefix}confusion_matrix.png"), bbox_inches="tight")
    plt.close()

    final_model = RandomForestClassifier(
        n_estimators=500, random_state=RANDOM_STATE, class_weight="balanced"
    )
    final_model.fit(X, y)
    model_path = os.path.join(MODELS_DIR, f"{model_prefix}_{name}_rf.joblib")
    joblib.dump({"model": final_model, "feature_names": feature_names}, model_path)
    print(f"\nSaved final model to {model_path}")

    importance_df = pd.DataFrame({
        "feature": feature_names,
        "importance": final_model.feature_importances_,
    }).sort_values("importance", ascending=False)

    plt.figure(figsize=(8, 5))
    plt.barh(importance_df["feature"], importance_df["importance"])
    plt.gca().invert_yaxis()
    plt.xlabel("Importance")
    plt.title(f"{component_label} - {name} feature importance (final Random Forest)")
    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, f"{prefix}feature_importance.png"), bbox_inches="tight")
    plt.close()

    metrics = {
        "n_recordings": int(len(df)),
        "n_pd": int(sum(df["label"] == 1)),
        "n_hc": int(sum(df["label"] == 0)),
        "n_participants": int(df["participant_id"].nunique()),
        "cv_splits": n_splits,
        "cv_summary": cv_summary,
        "random_forest_cv_accuracy": float(accuracy),
        "random_forest_cv_classification_report": report,
        "random_forest_cv_confusion_matrix": cm.tolist(),
    }
    metrics_path = os.path.join(results_dir, f"{prefix}metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics to {metrics_path}")

    return metrics, model_path
