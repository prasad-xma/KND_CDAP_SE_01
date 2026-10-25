"""Component 1 robustness experiment: does degrading a smartphone recording
change (a) the extracted phonation features and (b) Component 2's PD/HC
prediction, relative to the clean recording?

Directly tests the research question in the proposal: "How robust are
Parkinson's-related acoustic biomarkers under realistic smartphone recording
conditions?" Uses Component 2's own feature extractor and trained
vowel-combined model — i.e. this measures whether Component 2's pipeline,
specifically, would still work on a noisy/reverberant/compressed recording.

Usage:
    python -m src.component1_robustness.experiment
"""

import os
import glob
import tempfile

import numpy as np
import pandas as pd
import joblib
import soundfile as sf
import librosa
import matplotlib.pyplot as plt

from .degradation import (
    add_white_noise,
    add_synthetic_reverb,
    simulate_compression,
    apply_gain,
)
from ..component2_phonation.features import extract_phonation_features, FEATURE_NAMES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component1_robustness")
MODEL_PATH = os.path.join(REPO_ROOT, "models", "component2_phonation_vowel_combined_rf.joblib")
AH_RAW_DIR = os.path.join(REPO_ROOT, "data", "vowel_task", "raw")

N_PER_CLASS = 15
RANDOM_STATE = 42

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

    return [(f, 1) for f in pd_sample] + [(f, 0) for f in hc_sample]


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


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    model_features = bundle["feature_names"]

    files = _sample_clean_files()
    print(f"Testing {len(files)} recordings ({sum(l == 1 for _, l in files)} PD / {sum(l == 0 for _, l in files)} HC)")
    print(f"Conditions: {[c for c, _ in CONDITIONS]}")

    rows = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for fi, (filepath, true_label) in enumerate(files):
            y, sr = librosa.load(filepath, sr=None, mono=True)
            print(f"[{fi + 1}/{len(files)}] {os.path.basename(filepath)}")

            clean_feats = None
            for cond_name, spec in CONDITIONS:
                degraded = _degrade(y, sr, spec)
                tmp_path = os.path.join(tmpdir, "degraded.wav")
                sf.write(tmp_path, degraded, sr)

                feats = extract_phonation_features(tmp_path)
                if feats is None:
                    print(f"  {cond_name}: no voiced frames, skipped")
                    continue

                X = pd.DataFrame([feats])[model_features]
                pred = int(model.predict(X)[0])
                proba_pd = float(model.predict_proba(X)[0][1])

                if cond_name == "clean":
                    clean_feats = feats
                    clean_pred = pred

                row = {
                    "filename": os.path.basename(filepath),
                    "true_label": true_label,
                    "condition": cond_name,
                    "prediction": pred,
                    "proba_pd": proba_pd,
                }
                row.update({f"feat_{k}": v for k, v in feats.items()})
                rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "robustness_raw_results.csv"), index=False)

    clean_df = df[df["condition"] == "clean"][["filename", "prediction"] + [f"feat_{f}" for f in FEATURE_NAMES]]
    clean_df = clean_df.rename(columns={"prediction": "clean_prediction", **{f"feat_{f}": f"clean_{f}" for f in FEATURE_NAMES}})
    merged = df.merge(clean_df, on="filename")

    merged["prediction_unchanged"] = merged["prediction"] == merged["clean_prediction"]
    merged["correct_vs_ground_truth"] = merged["prediction"] == merged["true_label"]

    summary = merged.groupby("condition").agg(
        n=("filename", "count"),
        accuracy=("correct_vs_ground_truth", "mean"),
        prediction_agreement_with_clean=("prediction_unchanged", "mean"),
    ).reindex([c for c, _ in CONDITIONS])

    print("\n=== Robustness summary ===")
    print(summary)
    summary.to_csv(os.path.join(RESULTS_DIR, "robustness_summary.csv"))

    feature_drift_rows = []
    for feat in FEATURE_NAMES:
        merged[f"drift_{feat}"] = np.abs(merged[f"feat_{feat}"] - merged[f"clean_{feat}"]) / (np.abs(merged[f"clean_{feat}"]) + 1e-6)
        by_cond = merged.groupby("condition")[f"drift_{feat}"].mean()
        for cond in by_cond.index:
            feature_drift_rows.append({"condition": cond, "feature": feat, "mean_relative_drift": by_cond[cond]})
    drift_df = pd.DataFrame(feature_drift_rows)
    drift_df.to_csv(os.path.join(RESULTS_DIR, "feature_drift.csv"), index=False)

    plt.figure(figsize=(10, 5))
    plot_order = [c for c, _ in CONDITIONS if c != "clean"]
    plt.plot(plot_order, summary.loc[plot_order, "prediction_agreement_with_clean"], marker="o", label="Prediction agreement with clean")
    plt.plot(plot_order, summary.loc[plot_order, "accuracy"], marker="s", label="Accuracy vs ground truth")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Proportion")
    plt.ylim(0, 1.05)
    plt.title("Component 1 - Robustness of Component 2's vowel model under degradation")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "robustness_accuracy.png"), bbox_inches="tight")
    plt.close()

    pivot = drift_df.pivot(index="feature", columns="condition", values="mean_relative_drift")[plot_order]
    plt.figure(figsize=(12, 6))
    plt.imshow(pivot.values, aspect="auto", cmap="viridis")
    plt.colorbar(label="Mean relative drift")
    plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.title("Component 1 - Feature drift under degradation (relative to clean)")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "feature_drift_heatmap.png"), bbox_inches="tight")
    plt.close()

    print(f"\nSaved results to {RESULTS_DIR}")


if __name__ == "__main__":
    main()
