"""Closes the "enhancement testing" gap from the proposal (slide 12 novelty:
"combines controlled degradation simulation, ENHANCEMENT TESTING, and a
reliability-flagging classifier"; slide 16 validation metrics: "SNR, PESQ and
STOI improvement after enhancement").

For each clean recording x each degradation condition (reusing
`experiment.py`'s conditions and sample), this compares WITHOUT enhancement
vs WITH enhancement (`enhancement.py`) on:
  - blind SNR estimate (quality_gate.py)
  - STOI vs the clean reference (short-time objective intelligibility,
    0-1, higher = more intelligible) — always available, no extra install
  - PESQ vs the clean reference (perceptual speech quality, roughly -0.5 to
    4.5) — needs the `pesq` package, which requires a C compiler on Windows
    but installs cleanly on Colab/Linux; skipped gracefully if unavailable
  - Component 2's PD/HC prediction agreement with the clean recording's
    prediction (does enhancement actually help the downstream model, not
    just "sound cleaner"?)

Usage:
    python -m src.component1_robustness.evaluate_enhancement
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

from .degradation import add_white_noise, add_synthetic_reverb, simulate_compression, apply_gain
from .enhancement import enhance_audio
from .quality_gate import estimate_quality_db
from ..component2_phonation.features import extract_phonation_features

try:
    from pystoi import stoi as _stoi
except ImportError:
    _stoi = None

try:
    from pesq import pesq as _pesq
except ImportError:
    _pesq = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(REPO_ROOT, "results", "component1_robustness")
MODEL_PATH = os.path.join(REPO_ROOT, "models", "component2_phonation_vowel_combined_rf.joblib")
AH_RAW_DIR = os.path.join(REPO_ROOT, "data", "vowel_task", "raw")

N_PER_CLASS = 15
RANDOM_STATE = 42
PESQ_SR = 16000  # pesq requires 8000 or 16000 Hz

CONDITIONS = [
    ("noise_snr_10db", ("noise", 10)),
    ("noise_snr_5db", ("noise", 5)),
    ("noise_snr_0db", ("noise", 0)),
    ("noise_snr_-5db", ("noise", -5)),
    ("reverb_mild_rt0.3", ("reverb", 0.3)),
    ("reverb_heavy_rt0.6", ("reverb", 0.6)),
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
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if _stoi is None:
        print("WARNING: pystoi not installed — STOI columns will be empty.")
    if _pesq is None:
        print("WARNING: pesq not installed (needs a C compiler on Windows; installs fine on "
              "Colab/Linux) — PESQ columns will be empty.")

    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    model_features = bundle["feature_names"]

    files = _sample_clean_files()
    print(f"Testing {len(files)} recordings x {len(CONDITIONS)} conditions x [degraded, enhanced]")

    rows = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for fi, (filepath, true_label) in enumerate(files):
            y, sr = librosa.load(filepath, sr=None, mono=True)
            print(f"[{fi + 1}/{len(files)}] {os.path.basename(filepath)}")

            clean_feats = extract_phonation_features(filepath)
            if clean_feats is None:
                continue
            clean_X = pd.DataFrame([clean_feats])[model_features]
            clean_pred = int(model.predict(clean_X)[0])

            for cond_name, spec in CONDITIONS:
                degraded = _degrade(y, sr, spec)
                degraded_path = os.path.join(tmpdir, "degraded.wav")
                sf.write(degraded_path, degraded, sr)

                enhanced, enh_sr = enhance_audio(degraded_path)

                for variant, signal in [("degraded", degraded), ("enhanced", enhanced)]:
                    variant_path = os.path.join(tmpdir, "variant.wav")
                    sf.write(variant_path, signal, sr)

                    feats = extract_phonation_features(variant_path)
                    if feats is None:
                        continue
                    X = pd.DataFrame([feats])[model_features]
                    pred = int(model.predict(X)[0])

                    quality_db, quality_method = estimate_quality_db(variant_path)
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
    df.to_csv(os.path.join(RESULTS_DIR, "enhancement_raw_results.csv"), index=False)

    summary = df.groupby(["condition", "variant"]).agg(
        n=("filename", "count"),
        mean_quality_db=("quality_db", "mean"),
        mean_stoi_vs_clean=("stoi_vs_clean", "mean"),
        mean_pesq_vs_clean=("pesq_vs_clean", "mean"),
        prediction_agreement_with_clean=("prediction_matches_clean", "mean"),
    )
    print("\n=== Enhancement summary (degraded vs enhanced) ===")
    print(summary)
    summary.to_csv(os.path.join(RESULTS_DIR, "enhancement_summary.csv"))

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
    plt.savefig(os.path.join(RESULTS_DIR, "enhancement_improvement.png"), bbox_inches="tight")
    plt.close()

    print(f"\nSaved results to {RESULTS_DIR}")


if __name__ == "__main__":
    main()
