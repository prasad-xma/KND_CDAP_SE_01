"""Per-clip reliability labels for training and testing the quality gate.

The old validation labelled every clip in a
condition the same way ("noise_snr_5db" -> unreliable for all 30 clips), even
though some clips survive that condition and others don't. Here each
(clip, condition) pair gets its OWN label from what actually happened to it:

    reliable  = Component 2's prediction is unchanged from the clean clip
                AND jitter, shimmer, hnr and mean_f0 stay within tolerance
    unreliable = anything else

Each row also holds every gate input (gate_models.gate_inputs: quality metrics,
MFCC means), so the gate models train on it directly.

Usage (from parkinson-speech-ai/):
    python -m component1_robustness.labels
"""

from pathlib import Path

import librosa
import pandas as pd

from component1_robustness.conditions import CONDITIONS, condition_rng, degrade
from component1_robustness.config import load_config, resolve_path
from component1_robustness.features_check import (  # noqa: F401  (NO_PREDICTION re-exported for benchmark.py)
    NO_PREDICTION, compare_features, load_component2_model, phonation_features, predict_component2,
)
from component1_robustness.gate_models import gate_inputs

LABELS_CSV_NAME = "gate_labels.csv"
GROUP_DIRS = {"PD_AH": "PD", "HC_AH": "HC"}   # raw_data sub-folder -> group
RELIABLE, UNRELIABLE = "reliable", "unreliable"


def label_clip(clean_feats: dict | None, degraded_feats: dict | None,
               clean_pred: int, degraded_pred: int, tolerances: dict[str, float]) -> str:
    """"reliable" only if the prediction is unchanged AND every toleranced feature is preserved."""
    if degraded_pred != clean_pred:
        return UNRELIABLE
    if not compare_features(clean_feats, degraded_feats, tolerances)["preserved"]:
        return UNRELIABLE
    return RELIABLE


def participant_id_from_path(path: Path) -> str:
    """One recording per participant in the AH dataset, so the file stem is the participant ID."""
    return Path(path).stem


def find_clips(raw_dir: Path) -> list[tuple[Path, str]]:
    """Sorted (path, group) pairs for every .wav in the PD_AH and HC_AH sub-folders."""
    clips = []
    for folder, group in GROUP_DIRS.items():
        clips += [(p, group) for p in sorted((raw_dir / folder).glob("*.wav"))]
    return clips


def _clip_rows(path: Path, group: str, model, feature_names: list[str], config: dict) -> list[dict]:
    """One row per condition for a single clip (empty if the clean clip has no voiced frames)."""
    y, sr = librosa.load(path, sr=None, mono=True)
    clean_feats = phonation_features(y, sr)
    if clean_feats is None:
        print(f"  Skipped {path.name}: no voiced frames in the clean clip, cannot label.")
        return []
    clean_pred, _ = predict_component2(model, feature_names, clean_feats)

    rows = []
    for cond_name, spec in CONDITIONS:
        degraded = degrade(y, sr, spec, condition_rng(config["seed"], path.name, cond_name))
        degraded_feats = phonation_features(degraded, sr)
        degraded_pred, _ = predict_component2(model, feature_names, degraded_feats)
        rows.append({
            "filename": path.name,
            "participant_id": participant_id_from_path(path),
            "group": group,
            "condition": cond_name,
            **gate_inputs(degraded, sr, config),
            "clean_prediction": clean_pred,
            "degraded_prediction": degraded_pred,
            "label": label_clip(clean_feats, degraded_feats, clean_pred, degraded_pred,
                                config["feature_tolerances"]),
        })
    return rows


def build_label_table(config: dict) -> pd.DataFrame | None:
    """Label every clip x condition and save results/.../gate_labels.csv.

    Returns the table, or None (with a message) if the raw dataset is missing.
    """
    raw_dir = resolve_path(config, "raw_data")
    clips = find_clips(raw_dir) if raw_dir.is_dir() else []
    if not clips:
        print(f"Dataset not found: no .wav files in {raw_dir / 'PD_AH'} or {raw_dir / 'HC_AH'}.\n"
              "Extract the vowel-task zip there (see data/vowel_task/README.md), then rerun.")
        return None

    model, feature_names = load_component2_model(config)

    rows = []
    for i, (path, group) in enumerate(clips, start=1):
        print(f"[{i}/{len(clips)}] {path.name} ({group})")
        rows += _clip_rows(path, group, model, feature_names, config)

    table = pd.DataFrame(rows)
    out_path = resolve_path(config, "results") / LABELS_CSV_NAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_path, index=False)
    print(f"\nSaved {len(table)} rows to {out_path}")
    print(table["label"].value_counts().to_string())
    return table


def main() -> None:
    build_label_table(load_config())


if __name__ == "__main__":
    main()
