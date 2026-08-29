"""Loader for the Italian Parkinson's Voice and Speech dataset (Dimauro & Girardi, 2019),
restricted to the sustained vowel /a/ task (codes VA1/VA2 — see FILE CODES.xlsx).

Only two of the three participant groups did the vowel task:
    - "22 Elderly Healthy Control" (age-matched control for the PD group)
    - "28 People with Parkinson's disease"
"15 Young Healthy Control" (age ~19-29) has no vowel recordings and is excluded
here anyway — mixing it in would reintroduce an age confound against the
40-80 year-old PD group.

Raw audio (real .wav files), so this reuses our own `extract_phonation_features`
— unlike the Sakar dataset, this CAN be merged with our other vowel-task data.
"""

import os
import re
import glob
import zipfile

import pandas as pd

from .features import extract_phonation_features, FEATURE_NAMES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data", "italian_pvs")
ZIP_PATH = os.path.join(DATA_DIR, "italian_pvs.zip")
RAW_DIR = os.path.join(DATA_DIR, "raw")

GROUP_LABELS = {
    "22 Elderly Healthy Control": 0,
    "28 People with Parkinson's disease": 1,
}

# task_code + obfuscated-name + AGE(2) + GENDER(1) + DATE(6 or 8 digits) + TIME(4)
_SUFFIX_RE = re.compile(r"(\d{2})([MF])(?:\d{6}|\d{8})(\d{4})\.wav$", re.IGNORECASE)


def ensure_extracted():
    """Extract only the vowel-/a/ (VA1/VA2) files from the two relevant groups."""
    if os.path.isdir(RAW_DIR) and glob.glob(os.path.join(RAW_DIR, "**", "VA*.wav"), recursive=True):
        return RAW_DIR

    os.makedirs(RAW_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        members = [
            n for n in zf.namelist()
            if any(n.startswith(g + "/") for g in GROUP_LABELS)
            and os.path.basename(n).upper().startswith(("VA1", "VA2"))
            and n.lower().endswith(".wav")
        ]
        zf.extractall(RAW_DIR, members=members)

    return RAW_DIR


def _parse_age_gender(filename):
    match = _SUFFIX_RE.search(filename)
    if not match:
        return None, None
    age = int(match.group(1))
    gender = match.group(2).upper()
    return age, gender


def build_italian_vowel_features(verbose=True):
    """Extract phonation features for every vowel-/a/ recording (VA1/VA2).

    Returns a DataFrame with columns: filename, participant_id, task, the 10
    phonation feature columns, label (1=PD, 0=HC), label_name, age, sex.
    """
    ensure_extracted()

    wav_files = sorted(glob.glob(os.path.join(RAW_DIR, "**", "VA*.wav"), recursive=True))

    rows = []
    for i, filepath in enumerate(wav_files):
        rel = os.path.relpath(filepath, RAW_DIR)
        parts = rel.split(os.sep)
        # The PD group has an extra numbered subfolder ("1-5", "6-10", ...)
        # between the group and person folders; the person folder is always
        # the one directly containing the file, i.e. the second-to-last part.
        group, person = parts[0], parts[-2]
        label = GROUP_LABELS[group]

        if verbose:
            print(f"[{i + 1}/{len(wav_files)}] {rel}")

        try:
            feats = extract_phonation_features(filepath)
        except Exception as exc:
            print(f"  ERROR extracting {filepath}: {exc}")
            continue
        if feats is None:
            print(f"  Skipped (no voiced frames): {filepath}")
            continue

        age, gender = _parse_age_gender(os.path.basename(filepath))

        feats["filename"] = rel
        feats["participant_id"] = f"ITA_{person}"
        feats["task"] = "SustainedVowelA"
        feats["label"] = label
        feats["label_name"] = "PD" if label == 1 else "HC"
        feats["age"] = age
        feats["sex"] = gender
        rows.append(feats)

    df = pd.DataFrame(rows)
    ordered_cols = ["filename", "participant_id", "task"] + FEATURE_NAMES + ["label", "label_name", "age", "sex"]
    return df[ordered_cols]
