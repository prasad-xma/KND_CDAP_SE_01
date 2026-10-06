# Component 1 — Acoustic Robustness & Noise Handling

Tests whether Component 2's phonation biomarkers/predictions survive
degraded smartphone recording conditions — directly implementing the
proposal's Component 1 research question.

- `degradation.py` — synthetic degradations (no external noise/RIR corpora
  needed): white/pink/babble-mix noise at a target SNR, synthetic
  exponential-decay reverb, a bandwidth+bit-depth compression proxy, and
  gain changes (distance/volume proxy). **These are proxies, not real
  recorded noise/measured RIRs/real codecs** — see the module docstring for
  exactly what's approximated and why (no ffmpeg/lame available in this
  environment, and no noise/RIR corpus was downloaded for phase 1). Swap in
  real corpora (e.g. MUSAN, a measured RIR set) before treating results here
  as final.
- `experiment.py` — takes a stratified sample of clean AH-dataset vowel
  recordings, degrades each one under 11 conditions, re-extracts Component
  2's features (`component2_phonation.features.extract_phonation_features`)
  and re-runs Component 2's trained `vowel_combined` model on each degraded
  version, and reports: does the PD/HC prediction flip vs. the clean
  recording, and how much does each feature drift.

```
python -m src.component1_robustness.experiment
```

Outputs land in `results/component1_robustness/`:
- `robustness_raw_results.csv` — every (file x condition) prediction + features
- `robustness_summary.csv` — accuracy / prediction-agreement per condition
- `feature_drift.csv`, `feature_drift_heatmap.png` — per-feature relative drift
- `robustness_accuracy.png` — accuracy & prediction-agreement vs. condition

## Reading the results

This deliberately reuses Component 2's real trained model rather than
building a separate "quality classifier" — the proposal's own framing is
"does preprocessing preserve PD-related information for downstream
analysis," which is best answered by testing the actual downstream model.
A condition where prediction-agreement-with-clean drops sharply is exactly
the kind of recording a future quality gate should flag as unreliable before
it reaches Component 2/3.
