"""Dataset loading for the Component 2 sustained-vowel /a/ ("AH") dataset.

Expects a single zip in data/vowel_task/ containing:
    Demographics_age_sex.xlsx   (columns: Sample ID, Label, Age, Sex)
    PD_AH.zip                   (PD_AH/*.wav)
    HC_AH.zip                   (HC_AH/*.wav)

Each row of Demographics_age_sex.xlsx's "Parselmouth" sheet is matched to its
audio file by exact filename (Sample ID == wav filename without ".wav").
"""

import os
import glob
import zipfile

import pandas as pd

from .features import extract_phonation_features, FEATURE_NAMES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data", "vowel_task")
RAW_DIR = os.path.join(DATA_DIR, "raw")
DEMOGRAPHICS_XLSX = os.path.join(RAW_DIR, "Demographics_age_sex.xlsx")

LABEL_MAP = {"PwPD": 1, "HC": 0}


def _find_outer_zip():
    zips = glob.glob(os.path.join(DATA_DIR, "*.zip"))
    if not zips:
        raise FileNotFoundError(
            f"No zip file found in {DATA_DIR}. Place the vowel-task zip there."
        )
    if len(zips) > 1:
        raise FileNotFoundError(
            f"Multiple zip files found in {DATA_DIR}: {zips}. Keep only one."
        )
    return zips[0]


def ensure_extracted():
    """Extract the outer zip and the nested PD_AH.zip / HC_AH.zip into data/vowel_task/raw/."""
    if os.path.isdir(os.path.join(RAW_DIR, "PD_AH")) and os.path.isdir(os.path.join(RAW_DIR, "HC_AH")):
        return RAW_DIR

    outer_zip = _find_outer_zip()
    os.makedirs(RAW_DIR, exist_ok=True)
    with zipfile.ZipFile(outer_zip, "r") as zf:
        zf.extractall(RAW_DIR)

    for inner_name in ["PD_AH.zip", "HC_AH.zip"]:
        inner_path = os.path.join(RAW_DIR, inner_name)
        if os.path.exists(inner_path):
            with zipfile.ZipFile(inner_path, "r") as zf:
                zf.extractall(RAW_DIR)

    return RAW_DIR


def build_vowel_features(verbose=True):
    """Extract phonation features for every PD/HC sustained-/a/ recording.

    Returns a DataFrame with columns: filename, participant_id, task, the 10
    phonation feature columns, label (1=PD, 0=HC), label_name, age, sex.
    """
    ensure_extracted()

    demo = pd.read_excel(DEMOGRAPHICS_XLSX, sheet_name="Parselmouth").set_index("Sample ID")

    wav_files = sorted(
        glob.glob(os.path.join(RAW_DIR, "PD_AH", "*.wav"))
        + glob.glob(os.path.join(RAW_DIR, "HC_AH", "*.wav"))
    )

    rows = []
    for i, filepath in enumerate(wav_files):
        sample_id = os.path.splitext(os.path.basename(filepath))[0]

        if sample_id not in demo.index:
            print(f"  Skipped (no demographics row): {filepath}")
            continue

        label_raw = demo.loc[sample_id, "Label"]
        if label_raw not in LABEL_MAP:
            print(f"  Skipped (unknown label '{label_raw}'): {filepath}")
            continue

        if verbose:
            print(f"[{i + 1}/{len(wav_files)}] {sample_id} ({label_raw})")

        try:
            feats = extract_phonation_features(filepath)
        except Exception as exc:
            print(f"  ERROR extracting {filepath}: {exc}")
            continue
        if feats is None:
            print(f"  Skipped (no voiced frames): {filepath}")
            continue

        label = LABEL_MAP[label_raw]
        feats["filename"] = sample_id
        # One recording per participant in this dataset (verified: 81 wavs == 81 demographics rows).
        feats["participant_id"] = sample_id
        feats["task"] = "SustainedVowelA"
        feats["label"] = label
        feats["label_name"] = "PD" if label == 1 else "HC"
        feats["age"] = demo.loc[sample_id, "Age"]
        feats["sex"] = demo.loc[sample_id, "Sex"]
        rows.append(feats)

    df = pd.DataFrame(rows)
    ordered_cols = ["filename", "participant_id", "task"] + FEATURE_NAMES + ["label", "label_name", "age", "sex"]
    return df[ordered_cols]
