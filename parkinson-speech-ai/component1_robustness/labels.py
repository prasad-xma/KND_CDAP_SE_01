"""Per-clip reliability labels for training and testing the quality gate.

The old validation labelled every clip in a
condition the same way ("noise_snr_5db" -> unreliable for all 30 clips), even
though some clips survive that condition and others don't. Here each
(clip, condition) pair gets its OWN label from what actually happened to it:

    reliable  = Component 2's prediction is unchanged from the clean clip
                AND its P(PD) moved by at most labels.max_pd_probability_shift
                (and, only with labels.rule "prediction_and_features", jitter,
                shimmer, hnr and mean_f0 also stay within feature_tolerances)
    unreliable = anything else

Why the default rule is "prediction" (config v1.6): with the feature rule, every
noisy clip was labelled unreliable, even at 10 dB where Component 2 kept its
answer 80% of the time, because HNR always moved more than the PLACEHOLDER 15%
tolerance. The gate was being taught to reject recordings Component 2 handles
fine. Reliability now means "Component 2 gives the same answer, with about the
same confidence". Without a `labels:` section in the config, the old rule is used.

Each row also holds every gate input (gate_models.gate_inputs: quality metrics,
MFCC means), so the gate models train on it directly.

Usage (from parkinson-speech-ai/):
    python -m component1_robustness.labels
"""

from pathlib import Path

import math

import librosa
import pandas as pd

from component1_robustness.conditions import CONDITIONS, condition_rng, degrade, find_clips
from component1_robustness.config import load_config, resolve_path
from component1_robustness.features_check import (
    compare_features, load_component2_model, phonation_features, predict_component2,
)
from component1_robustness.gate_models import gate_inputs

LABELS_CSV_NAME = "gate_labels.csv"
RELIABLE, UNRELIABLE = "reliable", "unreliable"
RULE_PREDICTION = "prediction"                            # default from config v1.6
RULE_PREDICTION_AND_FEATURES = "prediction_and_features"  # the original rule
LABEL_RULES = (RULE_PREDICTION, RULE_PREDICTION_AND_FEATURES)
NO_PROBABILITY = -1.0   # written to the CSV when Component 2 found no voiced frames


def label_settings(config: dict) -> tuple[bool, float | None]:
    """(require_features, max_pd_probability_shift) from config["labels"].

    No `labels:` section -> the original rule (features required, no probability check).
    """
    section = config.get("labels")
    if not section:
        return True, None
    rule = section.get("rule", RULE_PREDICTION)
    if rule not in LABEL_RULES:
        raise ValueError(f"labels.rule must be one of {LABEL_RULES}, got {rule!r}")
    return rule == RULE_PREDICTION_AND_FEATURES, section.get("max_pd_probability_shift")


def label_clip(clean_feats: dict | None, degraded_feats: dict | None,
               clean_pred: int, degraded_pred: int, tolerances: dict[str, float], *,
               clean_p_pd: float = math.nan, degraded_p_pd: float = math.nan,
               max_p_shift: float | None = None, require_features: bool = True) -> str:
    """"reliable" only if Component 2 still gives the same answer with about the same confidence.

    Always: the prediction is unchanged.
    If max_p_shift is given: |P(PD) degraded - P(PD) clean| <= max_p_shift (NaN -> unreliable).
    If require_features: every toleranced feature is also preserved (the original rule).
    """
    if degraded_pred != clean_pred:
        return UNRELIABLE
    if max_p_shift is not None:
        shift = abs(degraded_p_pd - clean_p_pd)
        if math.isnan(shift) or shift > max_p_shift:
            return UNRELIABLE
    if require_features and not compare_features(clean_feats, degraded_feats, tolerances)["preserved"]:
        return UNRELIABLE
    return RELIABLE


def participant_id_from_path(path: Path) -> str:
    """One recording per participant in the AH dataset, so the file stem is the participant ID."""
    return Path(path).stem


def _clip_rows(path: Path, group: str, model, feature_names: list[str], config: dict) -> list[dict]:
    """One row per condition for a single clip (empty if the clean clip has no voiced frames)."""
    y, sr = librosa.load(path, sr=None, mono=True)
    clean_feats = phonation_features(y, sr)
    if clean_feats is None:
        print(f"  Skipped {path.name}: no voiced frames in the clean clip, cannot label.")
        return []
    clean_pred, clean_p_pd = predict_component2(model, feature_names, clean_feats)
    require_features, max_p_shift = label_settings(config)

    rows = []
    for cond_name, spec in CONDITIONS:
        degraded = degrade(y, sr, spec, condition_rng(config["seed"], path.name, cond_name))
        degraded_feats = phonation_features(degraded, sr)
        degraded_pred, degraded_p_pd = predict_component2(model, feature_names, degraded_feats)
        rows.append({
            "filename": path.name,
            "participant_id": participant_id_from_path(path),
            "group": group,
            "condition": cond_name,
            **gate_inputs(degraded, sr, config),
            "clean_prediction": clean_pred,
            "degraded_prediction": degraded_pred,
            "clean_p_pd": clean_p_pd,
            "degraded_p_pd": NO_PROBABILITY if math.isnan(degraded_p_pd) else degraded_p_pd,
            "label": label_clip(clean_feats, degraded_feats, clean_pred, degraded_pred,
                                config["feature_tolerances"], clean_p_pd=clean_p_pd,
                                degraded_p_pd=degraded_p_pd, max_p_shift=max_p_shift,
                                require_features=require_features),
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
    require_features, max_p_shift = label_settings(config)
    rule = RULE_PREDICTION_AND_FEATURES if require_features else RULE_PREDICTION
    print(f"\nLabel rule: {rule}, max P(PD) shift: {max_p_shift}")
    print(f"Saved {len(table)} rows to {out_path}")
    print(table["label"].value_counts().to_string())
    return table


def main() -> None:
    build_label_table(load_config())


if __name__ == "__main__":
    main()
