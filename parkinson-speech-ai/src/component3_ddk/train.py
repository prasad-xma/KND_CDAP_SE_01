"""Train and evaluate the Component 3 DDK baseline (Italian PVS, "pa"/"ta" repetition).

Usage:
    python -m src.component3_ddk.train
"""

import os

import pandas as pd

from .italian_ddk_dataset import build_italian_ddk_features
from .features import FEATURE_NAMES
from ..common.model_evaluation import run_baseline, REPO_ROOT

RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component3_ddk")
FEATURES_CSV = os.path.join(RESULTS_DIR, "italian_pvs_ddk_features.csv")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    if os.path.exists(FEATURES_CSV):
        print(f"Loading cached features from {FEATURES_CSV}")
        df = pd.read_csv(FEATURES_CSV)
    else:
        print("Extracting features from raw audio...")
        df = build_italian_ddk_features()
        df.to_csv(FEATURES_CSV, index=False)
        print(f"Saved features to {FEATURES_CSV}")

    print(f"\nTotal recordings: {len(df)} ({sum(df['syllable'] == 'pa')} pa / {sum(df['syllable'] == 'ta')} ta)")
    print(f"PD: {sum(df['label'] == 1)}  HC: {sum(df['label'] == 0)}")
    print(f"Unique participants: {df['participant_id'].nunique()}")
    print("\nAge by group:")
    print(df.groupby("label_name")["age"].describe()[["count", "mean", "std"]])

    run_baseline(
        df, name="ddk", prefix="ddk_", results_dir=RESULTS_DIR,
        feature_names=FEATURE_NAMES, model_prefix="component3_ddk", component_label="Component 3",
    )


if __name__ == "__main__":
    main()
