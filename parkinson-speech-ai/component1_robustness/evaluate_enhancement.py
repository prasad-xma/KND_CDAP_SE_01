"""Closes the "enhancement testing" gap from the proposal (slide 12 novelty:
"combines controlled degradation simulation, ENHANCEMENT TESTING, and a
reliability-flagging classifier"; slide 16 validation metrics: "SNR, PESQ and
STOI improvement after enhancement").

For each clean recording x each degradation condition (reusing
`experiment.py`'s conditions and sample), this compares WITHOUT enhancement
vs WITH enhancement (`enhancement.py`) on:
  - blind SNR estimate (quality_metrics.py)
  - STOI vs the clean reference (short-time objective intelligibility,
    0-1, higher = more intelligible) — always available, no extra install
  - PESQ vs the clean reference (perceptual speech quality, roughly -0.5 to
    4.5) — needs the `pesq` package, which requires a C compiler on Windows
    but installs cleanly on Colab/Linux; skipped gracefully if unavailable
  - Component 2's PD/HC prediction agreement with the clean recording's
    prediction (does enhancement actually help the downstream model, not
    just "sound cleaner"?)

Usage:
    python -m component1_robustness.evaluate_enhancement
"""

import os

import pandas as pd
import librosa
import matplotlib.pyplot as plt

from component1_robustness.conditions import CONDITIONS, condition_rng, degrade, sample_clean_files
from component1_robustness.config import load_config, resolve_path
from component1_robustness.enhancement import enhance
from component1_robustness.features_check import (
    NO_PREDICTION, load_component2_model, phonation_features, predict_component2,
)
from component1_robustness.quality_metrics import estimate_quality_db

try:
    from pystoi import stoi as _stoi
except ImportError:
    _stoi = None

try:
    from pesq import pesq as _pesq
except ImportError:
    _pesq = None

PESQ_SR = 16000  # pesq requires 8000 or 16000 Hz

# The enhancement study uses a subset of the shared CONDITIONS (same specs,
# same names): "clean" has nothing to enhance, and the two milder
# compression levels are skipped to keep run time down.
SKIPPED_CONDITIONS = {"clean", "compression_high", "compression_medium"}
ENHANCEMENT_CONDITIONS = [(name, spec) for name, spec in CONDITIONS if name not in SKIPPED_CONDITIONS]


def _safe_stoi(clean, other, sr):
    if _stoi is None:
        return None
    n = min(len(clean), len(other))
    return float(_stoi(clean[:n], other[:n], sr, extended=False))


def _safe_pesq(clean, other, sr):
    if _pesq is None:
        return None
    clean_rs = librosa.resample(clean, orig_sr=sr, target_sr=PESQ_SR)
    other_rs = librosa.resample(other, orig_sr=sr, target_sr=PESQ_SR)
    n = min(len(clean_rs), len(other_rs))
    try:
        return float(_pesq(PESQ_SR, clean_rs[:n], other_rs[:n], "wb"))
    except Exception:
        return None


def main():
    config = load_config()
    results_dir = resolve_path(config, "results")
    results_dir.mkdir(parents=True, exist_ok=True)
    if _stoi is None:
        print("WARNING: pystoi not installed — STOI columns will be empty.")
    if _pesq is None:
        print("WARNING: pesq not installed (needs a C compiler on Windows; installs fine on "
              "Colab/Linux) — PESQ columns will be empty.")

    model, model_features = load_component2_model(config)

    seed = config["seed"]
    method = config["enhancement_method"]   # same cleaning the pipeline uses
    files = sample_clean_files(seed, resolve_path(config, "raw_data"))
    print(f"Testing {len(files)} recordings x {len(ENHANCEMENT_CONDITIONS)} conditions x [degraded, enhanced]")

    rows = []
    for fi, (filepath, true_label) in enumerate(files):
        y, sr = librosa.load(filepath, sr=None, mono=True)
        print(f"[{fi + 1}/{len(files)}] {os.path.basename(filepath)}")

        clean_pred, _ = predict_component2(model, model_features, phonation_features(y, sr))
        if clean_pred == NO_PREDICTION:
            continue

        for cond_name, spec in ENHANCEMENT_CONDITIONS:
            degraded = degrade(y, sr, spec, condition_rng(seed, os.path.basename(filepath), cond_name))
            enhanced = enhance(degraded, sr, method, seed)

            for variant, signal in [("degraded", degraded), ("enhanced", enhanced)]:
                feats = phonation_features(signal, sr)
                if feats is None:
                    continue
                pred, _ = predict_component2(model, model_features, feats)

                quality_db, quality_method = estimate_quality_db(signal, sr)
                rows.append({
                    "filename": os.path.basename(filepath),
                    "true_label": true_label,
                    "condition": cond_name,
                    "variant": variant,
                    "quality_db": quality_db,
                    "quality_method": quality_method,
                    "stoi_vs_clean": _safe_stoi(y, signal, sr),
                    "pesq_vs_clean": _safe_pesq(y, signal, sr),
                    "prediction": pred,
                    "prediction_matches_clean": pred == clean_pred,
                })

    df = pd.DataFrame(rows)
    df.to_csv(results_dir / "enhancement_raw_results.csv", index=False)

    summary = df.groupby(["condition", "variant"]).agg(
        n=("filename", "count"),
        mean_quality_db=("quality_db", "mean"),
        mean_stoi_vs_clean=("stoi_vs_clean", "mean"),
        mean_pesq_vs_clean=("pesq_vs_clean", "mean"),
        prediction_agreement_with_clean=("prediction_matches_clean", "mean"),
    )
    print("\n=== Enhancement summary (degraded vs enhanced) ===")
    print(summary)
    summary.to_csv(results_dir / "enhancement_summary.csv")

    pivot_agreement = summary["prediction_agreement_with_clean"].unstack("variant")
    pivot_snr = summary["mean_quality_db"].unstack("variant")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    pivot_agreement.plot(kind="bar", ax=axes[0])
    axes[0].set_title("Prediction agreement with clean: degraded vs enhanced")
    axes[0].set_ylabel("Proportion")
    axes[0].set_ylim(0, 1.05)
    axes[0].tick_params(axis="x", rotation=45)

    pivot_snr.plot(kind="bar", ax=axes[1])
    axes[1].set_title("Estimated quality (SNR/HNR dB): degraded vs enhanced")
    axes[1].set_ylabel("dB")
    axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(results_dir / "enhancement_improvement.png", bbox_inches="tight")
    plt.close()

    print(f"\nSaved results to {results_dir}")


if __name__ == "__main__":
    main()
