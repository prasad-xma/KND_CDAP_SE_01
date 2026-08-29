"""Train and evaluate the Component 2 phonation baseline on the sustained-vowel /a/ dataset.

Usage:
    python -m src.component2_phonation.train_vowel
"""

import os

import pandas as pd

from .vowel_dataset import build_vowel_features
from .features import FEATURE_NAMES
from ..common.model_evaluation import run_baseline, REPO_ROOT

RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component2_phonation")
FEATURES_CSV = os.path.join(RESULTS_DIR, "vowel_a_features.csv")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    if os.path.exists(FEATURES_CSV):
        print(f"Loading cached features from {FEATURES_CSV}")
        df = pd.read_csv(FEATURES_CSV)
    else:
        print("Extracting features from raw audio (this may take a while)...")
        df = build_vowel_features()
        df.to_csv(FEATURES_CSV, index=False)
        print(f"Saved features to {FEATURES_CSV}")

    print(f"\nTotal recordings: {len(df)}")
    print(f"PD: {sum(df['label'] == 1)}  HC: {sum(df['label'] == 0)}")
    print(f"Unique participants: {df['participant_id'].nunique()}")
    print("\nAge by group:")
    print(df.groupby("label_name")["age"].describe()[["count", "mean", "std", "min", "max"]])
    print(
        "\nNOTE: PD and HC groups are not age-matched in this dataset. Any accuracy here "
        "may partly reflect age-related voice changes rather than PD-specific pathology "
        "— call this out explicitly if this baseline is reported."
    )

    run_baseline(
        df, name="vowel", prefix="vowel_", results_dir=RESULTS_DIR,
        feature_names=FEATURE_NAMES, model_prefix="component2_phonation", component_label="Component 2",
    )


if __name__ == "__main__":
    main()
