"""Train and evaluate a Component 2 baseline on the Sakar et al. (2018) dataset.

Usage:
    python -m src.component2_phonation.train_sakar
"""

import os

from .sakar_dataset import load_sakar_features
from ..common.model_evaluation import run_baseline, REPO_ROOT

RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component2_phonation")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    df, feature_names = load_sakar_features()

    print(f"Total recordings: {len(df)}")
    print(f"PD: {sum(df['label'] == 1)}  HC: {sum(df['label'] == 0)}")
    print(f"Unique participants: {df['participant_id'].nunique()}")
    print(f"Feature count: {len(feature_names)}")
    print(
        "\nNOTE: 3 recordings per participant. CV groups by participant_id, so no "
        "participant appears in both train and test folds within a run."
    )

    run_baseline(
        df, name="sakar", prefix="sakar_", results_dir=RESULTS_DIR, feature_names=feature_names,
        model_prefix="component2_phonation", component_label="Component 2",
    )


if __name__ == "__main__":
    main()
