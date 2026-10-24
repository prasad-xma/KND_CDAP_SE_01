"""Loader for the Kaggle "Parkinson's Voice Dataset"
(ucimachinelearning/parkinsons-voice-dataset, CC0). Not used in the
production model - duration/loudness predict its labels better than any
acoustic feature, so it's excluded until re-verified.
"""

import os
import glob
import zipfile

import pandas as pd

from .features import extract_phonation_features, FEATURE_NAMES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data", "vowel_task")
ZIP_PATH = os.path.join(REPO_ROOT, "data", "zip_files", "Kaggle.zip")
RAW_DIR = os.path.join(DATA_DIR, "raw", "kaggle_voice")

LABEL_MAP = {"Healthy": 0, "Parkinsons": 1}


def ensure_extracted():
    if os.path.isdir(os.path.join(RAW_DIR, "Voice_Dataset")):
        return RAW_DIR

    if not os.path.exists(ZIP_PATH):
        raise FileNotFoundError(f"Dataset zip not found at {ZIP_PATH}.")

    os.makedirs(RAW_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(RAW_DIR)

    return RAW_DIR


def build_kaggle_vowel_features(verbose=True):
    ensure_extracted()

    wav_files = []
    for group, label in LABEL_MAP.items():
        files = sorted(glob.glob(os.path.join(RAW_DIR, "Voice_Dataset", group, "*.wav")))
        wav_files.extend((f, label) for f in files)

    rows = []
    for i, (filepath, label) in enumerate(wav_files):
        filename = os.path.basename(filepath)

        if verbose:
            print(f"[{i + 1}/{len(wav_files)}] {filename}")

        try:
            feats = extract_phonation_features(filepath)
        except Exception as exc:
            print(f"  ERROR extracting {filepath}: {exc}")
            continue
        if feats is None:
            print(f"  Skipped (no voiced frames): {filepath}")
            continue

        feats["filename"] = filename
        feats["participant_id"] = f"KAGGLE_{os.path.splitext(filename)[0]}"
        feats["task"] = "SustainedVowelA"
        feats["label"] = label
        feats["label_name"] = "PD" if label == 1 else "HC"
        rows.append(feats)

    df = pd.DataFrame(rows)
    ordered_cols = ["filename", "participant_id", "task"] + FEATURE_NAMES + ["label", "label_name"]
    return df[ordered_cols]
