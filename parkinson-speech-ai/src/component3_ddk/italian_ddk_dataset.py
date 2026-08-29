"""Loader for the Italian Parkinson's Voice and Speech dataset's DDK task
(codes D1 = "pa" repetition, D2 = "ta" repetition, 5 sec each — see FILE CODES.xlsx).

Same source zip as Component 2's italian_pvs_dataset.py (data/italian_pvs/),
same two groups: "22 Elderly Healthy Control" and "28 People with Parkinson's disease"
("15 Young Healthy Control" has no DDK recordings and is excluded — and would
be age-mismatched against PD anyway).
"""

import os
import re
import glob
import zipfile

import pandas as pd

from .features import extract_ddk_features, FEATURE_NAMES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data", "italian_pvs")
ZIP_PATH = os.path.join(DATA_DIR, "italian_pvs.zip")
RAW_DIR = os.path.join(DATA_DIR, "raw")

GROUP_LABELS = {
    "22 Elderly Healthy Control": 0,
    "28 People with Parkinson's disease": 1,
}

_SUFFIX_RE = re.compile(r"(\d{2})([MF])(?:\d{6}|\d{8})(\d{4})\.wav$", re.IGNORECASE)


def ensure_extracted():
    """Extract only the DDK (D1/D2) files from the two relevant groups."""
    if os.path.isdir(RAW_DIR) and glob.glob(os.path.join(RAW_DIR, "**", "D[12]*.wav"), recursive=True):
        return RAW_DIR

    os.makedirs(RAW_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        members = [
            n for n in zf.namelist()
            if any(n.startswith(g + "/") for g in GROUP_LABELS)
            and os.path.basename(n).upper().startswith(("D1", "D2"))
            and n.lower().endswith(".wav")
        ]
        zf.extractall(RAW_DIR, members=members)

    return RAW_DIR


def _parse_age_gender(filename):
    match = _SUFFIX_RE.search(filename)
    if not match:
        return None, None
    return int(match.group(1)), match.group(2).upper()


def build_italian_ddk_features(verbose=True):
    """Extract DDK features for every D1/D2 ("pa"/"ta") recording.

    Returns a DataFrame with columns: filename, participant_id, task, syllable,
    the 12 DDK feature columns, label (1=PD, 0=HC), label_name, age, sex.
    """
    ensure_extracted()

    wav_files = sorted(glob.glob(os.path.join(RAW_DIR, "**", "D[12]*.wav"), recursive=True))

    rows = []
    for i, filepath in enumerate(wav_files):
        rel = os.path.relpath(filepath, RAW_DIR)
        parts = rel.split(os.sep)
        # The PD group has an extra numbered subfolder ("1-5", "6-10", ...)
        # between the group and person folders; the person folder is always
        # the one directly containing the file, i.e. the second-to-last part.
        group, person = parts[0], parts[-2]
        label = GROUP_LABELS[group]
        syllable = "pa" if os.path.basename(filepath).upper().startswith("D1") else "ta"

        if verbose:
            print(f"[{i + 1}/{len(wav_files)}] {rel}")

        try:
            feats = extract_ddk_features(filepath)
        except Exception as exc:
            print(f"  ERROR extracting {filepath}: {exc}")
            continue
        if feats is None:
            print(f"  Skipped (too few onsets detected): {filepath}")
            continue

        age, gender = _parse_age_gender(os.path.basename(filepath))

        feats["filename"] = rel
        feats["participant_id"] = f"ITA_{person}"
        feats["task"] = "DDK"
        feats["syllable"] = syllable
        feats["label"] = label
        feats["label_name"] = "PD" if label == 1 else "HC"
        feats["age"] = age
        feats["sex"] = gender
        rows.append(feats)

    df = pd.DataFrame(rows)
    ordered_cols = ["filename", "participant_id", "task", "syllable"] + FEATURE_NAMES + ["label", "label_name", "age", "sex"]
    return df[ordered_cols]
