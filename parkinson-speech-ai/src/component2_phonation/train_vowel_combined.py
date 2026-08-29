"""Train and evaluate Component 2 on the COMBINED sustained-vowel /a/ data:
our own "AH" dataset (data/vowel_task/) + the Italian Parkinson's Voice and
Speech dataset's vowel task (data/italian_pvs/, Elderly HC + PD groups only).

Both are raw audio processed through the same `extract_phonation_features`,
so — unlike the Sakar CSV, which has an incompatible precomputed feature set —
these two genuinely merge into one feature table. The vowel task itself
(sustained "aaaaaa") carries no language content, so combining English/Italian
recordings is methodologically defensible for this specific task, even though
it would not be for a reading or DDK task.

Usage:
    python -m src.component2_phonation.train_vowel_combined
"""

import os

import pandas as pd

from .vowel_dataset import build_vowel_features, ensure_extracted as ensure_ah_extracted
from .italian_pvs_dataset import build_italian_vowel_features, ensure_extracted as ensure_italian_extracted
from .features import FEATURE_NAMES
from ..common.model_evaluation import run_baseline, REPO_ROOT

RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component2_phonation")
AH_FEATURES_CSV = os.path.join(RESULTS_DIR, "vowel_a_features.csv")
ITALIAN_FEATURES_CSV = os.path.join(RESULTS_DIR, "italian_pvs_vowel_features.csv")


def _load_ah():
    if os.path.exists(AH_FEATURES_CSV):
        print(f"Loading cached AH-dataset features from {AH_FEATURES_CSV}")
        return pd.read_csv(AH_FEATURES_CSV)
    ensure_ah_extracted()
    df = build_vowel_features()
    df.to_csv(AH_FEATURES_CSV, index=False)
    return df


def _load_italian():
    if os.path.exists(ITALIAN_FEATURES_CSV):
        print(f"Loading cached Italian-dataset features from {ITALIAN_FEATURES_CSV}")
        return pd.read_csv(ITALIAN_FEATURES_CSV)
    ensure_italian_extracted()
    df = build_italian_vowel_features()
    df.to_csv(ITALIAN_FEATURES_CSV, index=False)
    return df


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    ah_df = _load_ah()
    ah_df["source"] = "AH_dataset"
    # AH participant_ids can collide with anything; keep them namespaced too.
    ah_df["participant_id"] = "AH_" + ah_df["participant_id"].astype(str)

    italian_df = _load_italian()
    italian_df["source"] = "Italian_PVS"

    combined = pd.concat([ah_df, italian_df], ignore_index=True)

    print(f"\nCombined total recordings: {len(combined)}")
    print(f"PD: {sum(combined['label'] == 1)}  HC: {sum(combined['label'] == 0)}")
    print(f"Unique participants: {combined['participant_id'].nunique()}")
    print("\nBy source:")
    print(combined.groupby(["source", "label_name"]).size())
    print("\nAge by source x label:")
    print(combined.groupby(["source", "label_name"])["age"].describe()[["count", "mean", "std"]])

    run_baseline(
        combined, name="vowel_combined", prefix="vowel_combined_", results_dir=RESULTS_DIR,
        feature_names=FEATURE_NAMES, model_prefix="component2_phonation", component_label="Component 2",
    )


if __name__ == "__main__":
    main()
