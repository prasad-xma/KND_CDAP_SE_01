"""Validates the quality gate against the proposal's own named metric (slide
16): "Quality-gate accuracy - precision/recall of the reliable-vs-unreliable
classifier against expert-labelled recordings."

No human-expert-labelled quality corpus exists for this project (no public
PD dataset ships per-recording quality ratings), so this uses the project's
own robustness study as the ground-truth source instead, and says so plainly
rather than calling it "expert-labelled": a condition counts as ground-truth
"reliable" if Component 2's prediction agreement with the clean recording
stayed >=0.7 in `experiment.py`'s results (robustness_summary.csv), and
"unreliable" otherwise. That threshold operationalises the proposal's own
framing of reliability ("do PD biomarkers survive?"), rather than an
arbitrary SNR/dB number.

Usage:
    python -m src.component1_robustness.validate_quality_gate
"""

import os
import glob
import tempfile

import numpy as np
import pandas as pd
import soundfile as sf
import librosa
from sklearn.metrics import precision_score, recall_score, accuracy_score, confusion_matrix

from .degradation import add_white_noise, add_synthetic_reverb, simulate_compression, apply_gain
from .quality_gate import check_quality

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component1_robustness")
AH_RAW_DIR = os.path.join(REPO_ROOT, "data", "vowel_task", "raw")
ROBUSTNESS_SUMMARY_PATH = os.path.join(RESULTS_DIR, "robustness_summary.csv")

N_PER_CLASS = 15
RANDOM_STATE = 42
GROUND_TRUTH_AGREEMENT_THRESHOLD = 0.7

CONDITIONS = [
    ("clean", None),
    ("noise_snr_10db", ("noise", 10)),
    ("noise_snr_5db", ("noise", 5)),
    ("noise_snr_0db", ("noise", 0)),
    ("noise_snr_-5db", ("noise", -5)),
    ("reverb_mild_rt0.3", ("reverb", 0.3)),
    ("reverb_heavy_rt0.6", ("reverb", 0.6)),
    ("compression_high", ("compression", "high")),
    ("compression_medium", ("compression", "medium")),
    ("compression_low", ("compression", "low")),
    ("distance_quiet_-6db", ("gain", -6)),
    ("distance_far_-12db", ("gain", -12)),
]


def _sample_clean_files():
    pd_files = sorted(glob.glob(os.path.join(AH_RAW_DIR, "PD_AH", "*.wav")))
    hc_files = sorted(glob.glob(os.path.join(AH_RAW_DIR, "HC_AH", "*.wav")))
    rng = np.random.default_rng(RANDOM_STATE)
    pd_sample = rng.choice(pd_files, size=min(N_PER_CLASS, len(pd_files)), replace=False)
    hc_sample = rng.choice(hc_files, size=min(N_PER_CLASS, len(hc_files)), replace=False)
    return list(pd_sample) + list(hc_sample)


def _degrade(y, sr, spec):
    if spec is None:
        return y
    kind, param = spec
    if kind == "noise":
        return add_white_noise(y, snr_db=param)
    if kind == "reverb":
        return add_synthetic_reverb(y, sr, rt60_sec=param)
    if kind == "compression":
        return simulate_compression(y, sr, level=param)
    if kind == "gain":
        return apply_gain(y, gain_db=param)
    raise ValueError(f"Unknown degradation kind: {kind}")


def _ground_truth_labels():
    """condition -> True (reliable) / False (unreliable), from the robustness study."""
    summary = pd.read_csv(ROBUSTNESS_SUMMARY_PATH, index_col="condition")
    return (summary["prediction_agreement_with_clean"] >= GROUND_TRUTH_AGREEMENT_THRESHOLD).to_dict()


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ground_truth = _ground_truth_labels()
    print("Ground-truth reliable/unreliable per condition (from robustness_summary.csv, "
          f"threshold={GROUND_TRUTH_AGREEMENT_THRESHOLD}):")
    for cond, reliable in ground_truth.items():
        print(f"  {cond:24s} {'RELIABLE' if reliable else 'unreliable'}")

    files = _sample_clean_files()
    print(f"\nEvaluating gate on {len(files)} recordings x {len(CONDITIONS)} conditions")

    rows = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for filepath in files:
            y, sr = librosa.load(filepath, sr=None, mono=True)
            for cond_name, spec in CONDITIONS:
                degraded = _degrade(y, sr, spec)
                tmp_path = os.path.join(tmpdir, "variant.wav")
                sf.write(tmp_path, degraded, sr)

                gate_result = check_quality(tmp_path)
                rows.append({
                    "filename": os.path.basename(filepath),
                    "condition": cond_name,
                    "ground_truth_reliable": ground_truth[cond_name],
                    "gate_predicted_reliable": gate_result.passed,
                    "estimated_quality_db": gate_result.estimated_snr_db,
                    "method": gate_result.method,
                })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "quality_gate_validation_raw.csv"), index=False)

    y_true = df["ground_truth_reliable"]
    y_pred = df["gate_predicted_reliable"]

    acc = accuracy_score(y_true, y_pred)
    # "Unreliable" is the class the gate exists to catch, so report precision/recall
    # for that class (pos_label=False, since True means reliable here).
    precision_unreliable = precision_score(y_true, y_pred, pos_label=False, zero_division=0)
    recall_unreliable = recall_score(y_true, y_pred, pos_label=False, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[False, True])

    print(f"\nQuality-gate accuracy vs ground truth: {acc:.4f}")
    print(f"Precision (catching truly unreliable recordings): {precision_unreliable:.4f}")
    print(f"Recall (catching truly unreliable recordings):    {recall_unreliable:.4f}")
    print("Confusion matrix [rows=ground truth, cols=predicted], order [unreliable, reliable]:")
    print(cm)

    metrics = {
        "ground_truth_source": "experiment.py robustness study "
                                f"(prediction_agreement_with_clean >= {GROUND_TRUTH_AGREEMENT_THRESHOLD} = reliable) "
                                "— NOT human-expert labels, no such corpus exists for this project.",
        "accuracy": float(acc),
        "precision_unreliable": float(precision_unreliable),
        "recall_unreliable": float(recall_unreliable),
        "confusion_matrix_order": ["unreliable", "reliable"],
        "confusion_matrix": cm.tolist(),
        "n_evaluations": int(len(df)),
    }
    metrics_path = os.path.join(RESULTS_DIR, "quality_gate_validation_metrics.json")
    import json
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
