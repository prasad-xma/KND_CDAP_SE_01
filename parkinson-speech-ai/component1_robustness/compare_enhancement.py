"""Which enhancement brings a noisy vowel back CLOSER TO ITS CLEAN ORIGINAL?

Independent of Component 2 (no model, no predictions): voice biomarkers are
measured directly with Praat, and every enhanced take is compared with the
clean recording it came from.

Procedure (deterministic, config seed):
  1. Each real sustained vowel in the AH dataset (data/vowel_task/raw) gets
     LEAD_IN_S of digital silence in front, like an app take where the user
     starts "aaaa" a moment after the timer.
  2. Each padded clip is degraded with the shared conditions (conditions.py):
     clean, white noise at 10 / 5 / 0 dB SNR; plus "hum_rumble_5db" (50 Hz mains
     hum and low-frequency rumble below 40 Hz, 5 dB SNR), the room noise a
     high-pass filter is meant for (white noise covers every frequency).
  3. Each degraded clip is processed by every method in METHODS.
  4. For jitter, shimmer, HNR, mean F0 and voice level (RMS, dB) we take the
     error vs the CLEAN clip: |value(processed) - value(clean)|, and compare it
     with doing nothing: a method helps when its error is smaller than the
     degraded clip's own error. SI-SDR vs clean is reported too.
  5. Speech-band contrast of the degraded clip is recorded, to choose the
     threshold above which enhancement is skipped.

Outputs (results/component1_robustness/):
  enhancement_comparison_raw.csv       one row per clip x condition x method
  enhancement_comparison_summary.csv   median error per biomarker, "% closer to clean"

Usage (from parkinson-speech-ai/):
    python -m component1_robustness.compare_enhancement
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import parselmouth
import soundfile as sf

from component1_robustness.conditions import CONDITIONS, condition_rng, degrade, find_clips
from component1_robustness.config import load_config, resolve_path
from component1_robustness.enhancement import enhance, noise_reference
from component1_robustness.quality_metrics import speech_band_contrast_db
from component2_phonation.features import F0_MAX_HZ, F0_MIN_HZ   # pitch range only, no model

LEAD_IN_S = 0.6
STUDY_CONDITIONS = ["clean", "noise_snr_10db", "noise_snr_5db", "noise_snr_0db", "hum_rumble_5db"]
HUM_SNR_DB = 5.0
BIOMARKERS = ["jitter_pct", "shimmer_pct", "hnr_db", "mean_f0_hz", "level_db"]

# (label, method, options). "stationary_ref" builds its noise sample from the take.
METHODS = [
    ("none", "none", {}),
    ("nonstationary (current)", "noisereduce_nonstationary", {}),
    ("nonstationary 0.6", "noisereduce_nonstationary", {"prop_decrease": 0.6}),
    ("stationary + noise sample", "noisereduce_stationary", {"noise_ref": "auto"}),
    ("stationary + noise sample 0.6", "noisereduce_stationary", {"noise_ref": "auto", "prop_decrease": 0.6}),
    ("highpass 80 Hz", "highpass", {"highpass_hz": 80.0}),
]


def biomarkers(y: np.ndarray, sr: int) -> dict:
    """Praat jitter (local, %), shimmer (local, %), HNR (dB), mean F0 (Hz) and RMS level (dB)."""
    sound = parselmouth.Sound(np.asarray(y, dtype=np.float64), sampling_frequency=sr)
    pitch = sound.to_pitch(time_step=0.01, pitch_floor=F0_MIN_HZ, pitch_ceiling=F0_MAX_HZ)
    points = parselmouth.praat.call(pitch, "To PointProcess")
    jitter = parselmouth.praat.call(points, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
    shimmer = parselmouth.praat.call([sound, points], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    hnr = parselmouth.praat.call(sound.to_harmonicity_cc(time_step=0.01, minimum_pitch=F0_MIN_HZ),
                                 "Get mean", 0, 0)
    f0 = pitch.selected_array["frequency"]
    f0 = f0[f0 > 0]
    return {
        "jitter_pct": 100 * jitter,
        "shimmer_pct": 100 * shimmer,
        "hnr_db": hnr,
        "mean_f0_hz": float(np.mean(f0)) if len(f0) else math.nan,
        "level_db": float(20 * np.log10(np.sqrt(np.mean(np.square(y))) + 1e-12)),
    }


def add_hum_rumble(y: np.ndarray, sr: int, rng: np.random.Generator, snr_db: float = HUM_SNR_DB) -> np.ndarray:
    """50 Hz mains hum + rumble (white noise low-passed at 40 Hz), scaled to snr_db vs y."""
    from scipy.signal import butter, sosfiltfilt
    t = np.arange(len(y)) / sr
    hum = np.sin(2 * np.pi * 50 * t + rng.uniform(0, 2 * np.pi))
    rumble = sosfiltfilt(butter(4, 40, btype="lowpass", fs=sr, output="sos"), rng.standard_normal(len(y)))
    noise = hum / np.std(hum) + rumble / np.std(rumble)
    voiced = y[np.abs(y) > 0]
    scale = np.sqrt(np.mean(voiced ** 2) / (np.mean(noise ** 2) * 10 ** (snr_db / 10)))
    return y + scale * noise


def make_condition(clean: np.ndarray, sr: int, cond: str, rng: np.random.Generator, specs: dict) -> np.ndarray:
    if cond == "hum_rumble_5db":
        return add_hum_rumble(clean, sr, rng)
    return degrade(clean, sr, specs[cond], rng)


def si_sdr(reference: np.ndarray, estimate: np.ndarray) -> float:
    """Scale-invariant signal-to-distortion ratio (dB) of estimate vs reference."""
    reference = reference - reference.mean()
    estimate = estimate - estimate.mean()
    target = (estimate @ reference) / (reference @ reference + 1e-12) * reference
    return float(10 * np.log10((target @ target) / ((estimate - target) @ (estimate - target) + 1e-12)))


def run_method(y: np.ndarray, sr: int, method: str, options: dict, seed: int) -> tuple[np.ndarray, bool | None]:
    """(processed signal, noise sample found?) — None when the method takes no noise sample."""
    opts = dict(options)
    found = None
    if opts.get("noise_ref") == "auto":
        opts["noise_ref"] = noise_reference(y, sr)
        found = opts["noise_ref"] is not None
    return enhance(y, sr, method, seed, **opts), found


def run_comparison(config: dict, max_clips: int | None = None) -> pd.DataFrame | None:
    clips = find_clips(resolve_path(config, "raw_data"))
    if not clips:
        print("Dataset not found: extract the AH vowels to data/vowel_task/raw (see data/vowel_task/README.md).")
        return None
    clips = clips[:max_clips] if max_clips else clips
    seed = config["seed"]
    specs = dict(CONDITIONS)
    rows = []
    for i, (path, group) in enumerate(clips, start=1):
        y, sr = sf.read(path, dtype="float64", always_2d=False)
        y = y.mean(axis=1) if y.ndim > 1 else y
        clean = np.concatenate([np.zeros(int(LEAD_IN_S * sr)), y])
        clean_bio = biomarkers(clean, sr)
        if math.isnan(clean_bio["jitter_pct"]):
            print(f"[{i}/{len(clips)}] {path.name}: no voice in the clean clip, skipped")
            continue
        print(f"[{i}/{len(clips)}] {path.name} ({group})")
        for cond in STUDY_CONDITIONS:
            degraded = make_condition(clean, sr, cond, condition_rng(seed, path.name, cond), specs)
            contrast = speech_band_contrast_db(degraded, sr)
            degraded_bio = biomarkers(degraded, sr)
            for label, method, options in METHODS:
                out, ref_found = run_method(degraded, sr, method, options, seed)
                bio = biomarkers(out, sr)
                row = {"filename": path.name, "group": group, "condition": cond, "method": label,
                       "contrast_db": contrast, "noise_sample_found": ref_found,
                       "si_sdr_db": si_sdr(clean, out)}
                for b in BIOMARKERS:
                    err, base_err = abs(bio[b] - clean_bio[b]), abs(degraded_bio[b] - clean_bio[b])
                    row[f"{b}_error"] = err
                    row[f"{b}_closer"] = err < base_err - 1e-9 if label != "none" else None
                    row[f"{b}_worse"] = err > base_err + 1e-9 if label != "none" else None
                rows.append(row)
    return pd.DataFrame(rows)


def summarise(raw: pd.DataFrame) -> pd.DataFrame:
    """Median error vs clean per biomarker, and % of clips moved closer to / further from clean."""
    agg = {"si_sdr_db": "median", **{f"{b}_error": "median" for b in BIOMARKERS}}
    summary = raw.groupby(["condition", "method"], sort=False).agg(agg)
    moved = raw[raw["method"] != "none"].copy()
    for b in BIOMARKERS:
        moved[f"{b}_closer"] = moved[f"{b}_closer"].astype(float)
        moved[f"{b}_worse"] = moved[f"{b}_worse"].astype(float)
    pct = moved.groupby(["condition", "method"], sort=False)[
        [f"{b}_closer" for b in BIOMARKERS] + [f"{b}_worse" for b in BIOMARKERS]].mean() * 100
    return summary.join(pct).round(3)


def main() -> None:
    config = load_config()
    raw = run_comparison(config)
    if raw is None:
        return
    out_dir = resolve_path(config, "results")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarise(raw)
    raw.to_csv(out_dir / "enhancement_comparison_raw.csv", index=False)
    summary.to_csv(out_dir / "enhancement_comparison_summary.csv")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(summary)
    print(f"\nSaved to {Path(out_dir)}")


if __name__ == "__main__":
    main()
