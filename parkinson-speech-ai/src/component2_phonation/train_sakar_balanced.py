"""Class-balanced Sakar et al. baseline: undersample PD participants to match HC count.

The raw Sakar dataset is 188 PD vs 64 HC participants (2.9:1) — training on all
of it gives high overall accuracy but poor HC recall (~51-54%), because the
model leans on the PD base rate rather than learning to discriminate. This
script randomly drops PD participants down to the HC count (64 vs 64,
i.e. 192 vs 192 recordings) so both classes get equal weight in training and
evaluation.

This is a stopgap for a small, honestly-reported demo number, not a fix for
the underlying data shortage — see Component 2's README. Phase 2 data
collection should aim to bring HC participant count up instead of permanently
throwing away PD data.

Usage:
    python -m src.component2_phonation.train_sakar_balanced
"""

import os

import pandas as pd

from .sakar_dataset import load_sakar_features
from ..common.model_evaluation import run_baseline, REPO_ROOT, RANDOM_STATE

RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component2_phonation")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    df, feature_names = load_sakar_features()

    pd_participants = df.loc[df["label"] == 1, "participant_id"].unique()
    hc_participants = df.loc[df["label"] == 0, "participant_id"].unique()

    n_keep = min(len(pd_participants), len(hc_participants))
    pd_keep = pd.Series(pd_participants).sample(n=n_keep, random_state=RANDOM_STATE).values

    keep_participants = set(pd_keep) | set(hc_participants)
    df = df[df["participant_id"].isin(keep_participants)].reset_index(drop=True)

    print(f"Balanced subsample: {len(df)} recordings")
    print(f"PD: {sum(df['label'] == 1)}  HC: {sum(df['label'] == 0)}")
    print(f"Unique participants: {df['participant_id'].nunique()} "
          f"({len(pd_keep)} PD, {len(hc_participants)} HC)")
    print(
        "\nNOTE: participant-level undersampling to fix Sakar's 2.9:1 PD:HC "
        "imbalance. CV still groups by participant_id (no leakage)."
    )

    run_baseline(
        df, name="sakar_balanced", prefix="sakar_balanced_", results_dir=RESULTS_DIR,
        feature_names=feature_names, model_prefix="component2_phonation",
        component_label="Component 2",
    )


if __name__ == "__main__":
    main()
