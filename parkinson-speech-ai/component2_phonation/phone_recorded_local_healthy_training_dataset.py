import os
import glob

import pandas as pd

from .features import extract_phonation_features, FEATURE_NAMES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR = os.path.join(REPO_ROOT, "data", "vowel_task", "raw", "phone_recorded_local_healthy_for_training")

_AUDIO_EXTENSIONS = (".wav", ".m4a", ".mp4", ".ogg", ".mp3")


def build_phone_recorded_local_healthy_training_features(verbose=True):
    files = sorted(
        f for f in glob.glob(os.path.join(RAW_DIR, "*"))
        if os.path.splitext(f)[1].lower() in _AUDIO_EXTENSIONS
    )

    rows = []
    for i, filepath in enumerate(files):
        filename = os.path.basename(filepath)
        participant_id = f"LOCAL_TRAIN_HC_{i + 1:02d}"

        if verbose:
            print(f"[{i + 1}/{len(files)}] {filename}")

        try:
            feats = extract_phonation_features(filepath)
        except Exception as exc:
            print(f"  ERROR extracting {filepath}: {exc}")
            continue
        if feats is None:
            print(f"  Skipped (no voiced frames): {filepath}")
            continue

        feats["filename"] = filename
        feats["participant_id"] = participant_id
        feats["task"] = "SustainedVowelA"
        feats["label"] = 0
        feats["label_name"] = "HC"
        rows.append(feats)

    df = pd.DataFrame(rows)
    ordered_cols = ["filename", "participant_id", "task"] + FEATURE_NAMES + ["label", "label_name"]
    return df[ordered_cols]
