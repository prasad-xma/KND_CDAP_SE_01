"""Dataset loading for the Component 2 MDVR-KCL baseline.

Handles extracting the local zip (parkinson-speech-ai/data/26_29_09_2017_KCL.zip)
and building a features dataframe for the ReadText task, PD vs HC.
"""

import os
import re
import zipfile
import glob

import pandas as pd

from .features import extract_phonation_features, FEATURE_NAMES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")
ZIP_PATH = os.path.join(DATA_DIR, "26_29_09_2017_KCL.zip")
RAW_DIR = os.path.join(DATA_DIR, "raw")
DATASET_ROOT = os.path.join(RAW_DIR, "26-29_09_2017_KCL")


def ensure_extracted(zip_path=ZIP_PATH, extract_to=RAW_DIR):
    """Extract the MDVR-KCL zip into data/raw/ if not already extracted."""
    if os.path.isdir(DATASET_ROOT):
        return DATASET_ROOT

    if not os.path.exists(zip_path):
        raise FileNotFoundError(
            f"Dataset zip not found at {zip_path}. Place 26_29_09_2017_KCL.zip in data/."
        )

    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    return DATASET_ROOT


def _participant_id(filename):
    match = re.match(r"(ID\d+)", os.path.basename(filename))
    return match.group(1) if match else os.path.basename(filename)


def build_readtext_features(dataset_root=None, verbose=True):
    """Extract phonation features for every ReadText PD/HC recording.

    Returns a DataFrame with columns: filename, participant_id, task,
    label (1=PD, 0=HC), label_name, and the 10 phonation feature columns.
    """
    dataset_root = dataset_root or ensure_extracted()

    pd_files = sorted(glob.glob(os.path.join(dataset_root, "ReadText", "PD", "*.wav")))
    hc_files = sorted(glob.glob(os.path.join(dataset_root, "ReadText", "HC", "*.wav")))

    rows = []
    for label, label_name, files in [(1, "PD", pd_files), (0, "HC", hc_files)]:
        for i, filepath in enumerate(files):
            if verbose:
                print(f"[{label_name} {i + 1}/{len(files)}] {os.path.basename(filepath)}")
            try:
                feats = extract_phonation_features(filepath)
            except Exception as exc:
                print(f"  ERROR extracting {filepath}: {exc}")
                continue
            if feats is None:
                print(f"  Skipped (no voiced frames): {filepath}")
                continue
            feats["filename"] = os.path.basename(filepath)
            feats["participant_id"] = _participant_id(filepath)
            feats["task"] = "ReadText"
            feats["label"] = label
            feats["label_name"] = label_name
            rows.append(feats)

    df = pd.DataFrame(rows)
    ordered_cols = ["filename", "participant_id", "task"] + FEATURE_NAMES + ["label", "label_name"]
    return df[ordered_cols]
