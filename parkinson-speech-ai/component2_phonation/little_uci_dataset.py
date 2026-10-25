"""Loader for the Little et al. (2008) UCI "Parkinsons" dataset
(https://archive.ics.uci.edu/dataset/174/parkinsons). Precomputed features
only (no raw audio), same pattern as sakar_dataset.py.
"""

import os
import re

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_PATH = os.path.join(REPO_ROOT, "data", "vowel_task", "little_uci_dataset", "parkinsons.data")

NON_FEATURE_COLS = ["name", "participant_id", "status"]
_PID_RE = re.compile(r"(S\d+)")


def load_little_uci_features():
    df = pd.read_csv(CSV_PATH)

    df["participant_id"] = df["name"].str.extract(_PID_RE)
    feature_names = [c for c in df.columns if c not in NON_FEATURE_COLS + ["status"]]

    df = df.rename(columns={"status": "label"}).copy()
    df["label_name"] = df["label"].map({1: "PD", 0: "HC"})

    ordered_cols = ["name", "participant_id"] + feature_names + ["label", "label_name"]
    return df[ordered_cols], feature_names
