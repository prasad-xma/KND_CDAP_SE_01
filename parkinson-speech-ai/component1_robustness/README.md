# Component 1 — Acoustic Robustness & Quality Gate

The first stage of the screening pipeline. It is a **quality gate, not a PD
classifier**: it decides whether a smartphone recording is good enough for
Components 2/3 to analyse, cleans it up if that is safe, and tells the user to
re-record if it is not.

All commands are run from `parkinson-speech-ai/`. Every seed, threshold and
path comes from `configs/component1.yaml` (fixed by the developer; the end
user only uploads audio).

## 1. Input

One recording (`.wav`, `.m4a` or `.mp3`) and its task: `vowel` (sustained
"aaaa", goes to Component 2) or `ddk` ("pa-ta-ka", goes to Component 3).
Valid length: 3.0–15.0 s.

```
python -m component1_robustness.cli --input recording.m4a --task vowel
```

or over HTTP (same style as Component 2's API):

```
uvicorn component1_robustness.api:app --reload --host 0.0.0.0 --port 8001
# POST /quality/check  (multipart: audio=<file>, task=vowel|ddk)   GET /health
```

## 2. Process

`pipeline.run_gate()` runs these steps, in order:

| Step | Module | What it does |
|---|---|---|
| Load | `common/audio_io.py`, `pipeline.py` | any format → mono WAV at 16 kHz |
| Duration check | `quality_metrics.check_duration` | outside 3–15 s → FAIL now, nothing else runs |
| Quality before | `gate_models.gate_inputs` | SNR or HNR, level, clipping, voice activity, MFCC means |
| Features before | `features_check.phonation_features` | Component 2's own 10 features (its code, not a copy) |
| Enhance | `enhancement.enhance` | `noisereduce` (non-stationary / stationary), `wiener`, or `none` |
| Quality / features after | as above | on the enhanced audio |
| Preservation check | `features_check.compare_features` | jitter, shimmer, HNR, mean F0 within relative tolerance? |
| Gate decision | `gate_models` | hard rules (duration, clipping, no voice), then the selected model |

**Which audio goes on:** if enhancement preserved the biomarkers, the gate
judges and forwards `enhanced.wav`; if not, it judges and forwards `raw.wav`
(enhancement altered the biomarkers, so the original is safer). On FAIL nothing
is forwarded.

**Gate models** (`gate_models.py`, all share `fit()` / `predict()`):

| Name | Model |
|---|---|
| `comp1-A` | Rule: SNR/HNR estimate ≥ 10 dB (the original rule, from the robustness study). |
| `comp1-B-rf` / `-svm` / `-logreg` | Classical ML on quality metrics + MFCC means. |

Training labels are **per clip** (`labels.py`): a degraded clip is
"reliable" only if Component 2's prediction is unchanged from the clean clip
AND jitter, shimmer, HNR and mean F0 stay within tolerance. The old
validation labelled every clip in a condition the same way.

```
python -m component1_robustness.labels      # build results/component1_robustness/gate_labels.csv
python -m component1_robustness.benchmark   # compare all gate models, pick one, write it to the config
```

The robustness study scripts (they produced the evidence for the 10 dB
threshold and the enhancement findings):
`python -m component1_robustness.experiment`,
`python -m component1_robustness.evaluate_enhancement`.

## 3. Output

Per recording, in `outputs/component1/<clip_id>/` (`clip_id` = file name +
first 8 hex digits of its SHA-256):

| File | Content |
|---|---|
| `raw.wav` | the standardised input (24-bit PCM, 16 kHz, mono) |
| `enhanced.wav` | after enhancement |
| `waveform.png`, `spectrogram.png` | raw above enhanced, shared scales, SNR/HNR in the titles |
| `report.json` | decision, quality_score (0–100), reason, quality and features before/after, preservation result, `audio_for_next_stage`, `audio_choice`, `next_component`, `user_message`, `input_sha256`, `config_version` |

No timestamps anywhere: the same input and config always give byte-identical
files. A rejected recording is a normal result (`"decision": "FAIL"` plus a
`user_message`), not an error.

Benchmark outputs in `results/component1_robustness/`: `gate_benchmark.csv`
(mean ± std over 5 participant-grouped folds, plus held-out test), 
`gate_benchmark_vs_snr.png`, `gate_benchmark_timing.csv`,
`selected_gate_model.json` (winner + the reason, step by step).

## 4. Verification

Automated and deterministic only: no manual listening.

```
pytest component1_robustness/tests          # the whole suite (~2 min)
python -m component1_robustness.demo        # 2 recordings + the suite + benchmark winner
```

| Kind | Where |
|---|---|
| Known-answer synthetic signals | `test_degradation.py` (exact SNR ±0.01 dB, gain ±0.01 dB), `test_quality_metrics.py` (duration limits, 5% clipping, silence/tone voice activity, SNR ±2 dB) |
| Controlled degradation with known labels | `test_labels.py`, `test_gate_models.py` |
| Sanity rules | every gate model: clean → PASS, noise / silence / clipped / too short / too long → FAIL; score never rises with more noise |
| Preservation | `test_features_check.py`, `test_pipeline.py` (tight tolerance → raw audio forwarded) |
| Reproducibility by hash | same input twice → identical `report.json`, WAVs and PNGs; same seed → identical benchmark CSV |
| Golden regression set | `tests/golden/`: 7 seeded clips (clean, 20/5/0 dB noise, clipped, 2.9 s, 15.1 s) and their expected reports; `test_golden_set.py` re-runs them (floats within 1e-6) |
| Benchmark correctness | `test_benchmark.py`: metrics equal a 10-row hand calculation exactly; no participant in both train and test |

The golden set uses a frozen config (`tests/golden/config_golden.yaml`) so it
tests the code, not the current tuning. Regenerate it only for an intended
change, then review the JSON diff:
`python component1_robustness/tests/golden/generate.py`.

## Known limitations

- **Synthetic degradations.** Noise is generated white noise,
  reverb is a synthetic exponential-decay impulse response rather than a
  measured room, and "compression" is low-pass + requantisation rather than a
  real codec.
- **No expert-labelled quality corpus.** No public PD dataset ships
  per-recording quality ratings, so "reliable" is defined by what happens to
  Component 2's prediction and biomarkers, not by human listeners.
- **Absolute level is not portable across devices.** Recording level (dBFS) is
  reported but not used to pass/fail: corpora recorded at different gain sit
  at different levels even when clean. Needs per-device calibration (Phase 2).
- **`noisereduce` removes sustained vowels.** Without a noise-only sample it
  takes the steady vowel for noise (keeps ~4–7% of its level on a synthetic
  test). The preservation check catches this and forwards the raw audio
  instead, but the default enhancement method should be chosen by the
  benchmark on real data.
- **Short dataset clips.** The AH vowel recordings are 1.7–5.5 s at 8 kHz; many
  are below the 3 s minimum. The benchmark switches the duration rule off
  (`benchmark.apply_duration_rule`) so it compares quality judgement only.
- **Sample rate for Component 2.** Audio is forwarded at 16 kHz. Component 2's
  zero-crossing features depend on sample rate; confirm the rate its model was
  trained on.
- **Placeholders still to calibrate:** `min_voice_activity_pct` and
  `feature_tolerances` in the config. Relative tolerances also break down for
  features near zero (e.g. jitter of a perfectly periodic signal).
- **Silence-based SNR on digitally silent pauses** reads low (~5 dB): all-zero
  frames are dropped before the noise floor is taken. Real recordings always
  have some background noise, so this mainly affects synthetic clips.
