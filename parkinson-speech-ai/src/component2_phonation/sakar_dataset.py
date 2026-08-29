"""Loader for the UCI "Parkinson's Disease Classification" dataset (Sakar et al., 2018).

Precomputed-features-only dataset: sustained vowel /a/, 252 participants
(188 PD, 64 HC), 3 recordings each, 752 acoustic features per recording
(jitter/shimmer variants, PPE, DFA, RPDE, MFCCs, TQWT wavelet features).
There is no raw audio, so `features.py` (our own extractor) is not used here
— we train directly on the dataset's own precomputed feature columns.

CSV quirk: row 0 of the raw file is a "Baseline Features" section-label row,
not data — the real header is row 1 (hence header=1 below).
"""

import os

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CSV_PATH = os.path.join(REPO_ROOT, "data", "sakar_pd_dataset", "pd_speech_features.csv")

NON_FEATURE_COLS = ["id", "gender", "class"]


def load_sakar_features():
    """Load the Sakar et al. dataset and return (df, feature_names).

    df has columns: participant_id, label (1=PD, 0=HC), label_name, gender,
    plus all 752 original acoustic feature columns.
    """
    df = pd.read_csv(CSV_PATH, header=1)

    feature_names = [c for c in df.columns if c not in NON_FEATURE_COLS]

    df = df.rename(columns={"id": "participant_id", "class": "label"}).copy()
    df["label_name"] = df["label"].map({1: "PD", 0: "HC"})

    ordered_cols = ["participant_id", "gender"] + feature_names + ["label", "label_name"]
    return df[ordered_cols], feature_names
