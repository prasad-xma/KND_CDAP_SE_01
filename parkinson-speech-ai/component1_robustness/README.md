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
Valid length: 1.5–5.0 s (the app records for 5 s).

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
| Duration check | `quality_metrics.check_duration` | outside 1.5–5 s → FAIL now, nothing else runs |
| Quality before | `gate_models.gate_inputs` | SNR or HNR, level, clipping, voice activity, MFCC means |
| Features before | `features_check.phonation_features` / `ddk_features` | the receiving component's own features (its code, not a copy): Component 2's 10 for `vowel`, Component 3's 12 for `ddk` |
| Enhance | `enhancement.enhance` | `noisereduce` (non-stationary / stationary), `wiener`, or `none` |
| Quality / features after | as above | on the enhanced audio |
| Preservation check | `features_check.compare_features` | `vowel`: jitter, shimmer, HNR, mean F0; `ddk`: DDK rate, mean IOI, CV of IOI, pause ratio — each within its relative tolerance? |
| Gate decision | `gate_models` | hard rules (duration, clipping, no voice), then the selected model |
| Voice presence | `voice_check.check_voice_presence` | flat speech band → FAIL `no_voice` (quiet) or `low_snr` (loud); see below |

**Why comp1-A changed (config v1.5).** Labelled real takes from a laptop mic
through the app showed HNR cannot separate a voice from steady room hum: the
user's real "aaaa"/"pa-ta-ka" scored HNR 7.5–9.5 dB (rejected as noisy) while
silent takes scored 9.6–10.0 dB. comp1-A now judges the **speech-band
contrast**: the 90th minus 10th percentile of per-frame energy in 300–3400 Hz
(voice formants, above hum and fan rumble). A voice starts and stops, so the
band varies; room noise stays flat. On 13 labelled real takes: voice 11–15 dB,
silence 2.3–3.4 dB.

**Voice presence check.** On the raw audio, after the gate model:
- contrast ≥ 6 dB → a voice is present; the gate decision stands.
- contrast < 6 dB (flat) and level < −30 dBFS → FAIL `no_voice` (quiet room, nobody spoke).
- contrast < 6 dB (flat) and level ≥ −30 dBFS → FAIL `low_snr` (loud steady noise drowned the voice).

It replaces a PASS or a quality FAIL (`low_snr`), so a silent take is told
"no voice" rather than "too noisy"; `too_short`, `too_long` and `clipped` are
kept. All thresholds are placeholders in `configs/component1.yaml`
(`comp1a_pass_db`, `voice_check`). Earlier attempts (v1.2–v1.4: Praat voicing
and voice activity after noise reduction) failed on real takes: hum looked up
to 87% "voiced", and noise reduction also removed the real sustained vowel.

**Task check** (`task_check.py`, config `task_check`, since v1.7). The gate
judges *how well* a take was recorded, not *what* was said, so clear gibberish
used to pass. On the raw audio, after the voice check: a vowel take passes only
if its longest unbroken voiced stretch is ≥ 1.0 s AND that stretch is ≥ 50% of
all voicing in the take (one held "aaaa", not many short syllables). Otherwise
a PASS becomes FAIL `wrong_task` ("say one steady 'aaaa'"). Calibrated on the 81
real AH dataset vowels (longest 1.31–7.16 s, share 0.58–1.00: none rejected)
and real app takes (real vowels 1.84–3.47 s pass; a gibberish take, 0.33 s,
fails). Pitch spread is recorded but not used: it did not separate gibberish
from real vowels. DDK is reported as not checked. Thresholds are PLACEHOLDERS
until more labelled wrong-task takes exist.

**Which audio goes on:** if enhancement preserved the biomarkers, the gate
judges and forwards `enhanced.wav`; if not, it judges and forwards `raw.wav`
(enhancement altered the biomarkers, so the original is safer). On FAIL nothing
is forwarded.

**Gate models** (`gate_models.py`, all share `fit()` / `predict()`):

| Name | Model |
|---|---|
| `comp1-A` | Rule: speech-band contrast ≥ 10 dB (since v1.5; until v1.4 SNR/HNR ≥ 10 dB from the robustness study). |
| `comp1-B-rf` / `-svm` / `-logreg` | Classical ML on quality metrics + MFCC means. |

Training labels are **per clip** (`labels.py`). Since config v1.6 a degraded
clip is "reliable" when Component 2 gives the **same answer with about the same
confidence**: the PD/HC prediction is unchanged AND P(PD) moved by at most
`labels.max_pd_probability_shift` (0.15). The earlier rule also required jitter,
shimmer, HNR and mean F0 to stay within the placeholder `feature_tolerances`;
with it, every noisy clip was labelled unreliable (even at 10 dB, where
Component 2 kept its answer 80% of the time), so the gate learned to reject
recordings Component 2 handles fine. Set `labels.rule: prediction_and_features`
to go back to it. The old validation labelled every clip in a condition the same way.

**Goal: good recordings must pass.** The benchmark tunes each gate's pass
threshold on out-of-fold development scores to the highest value that still
rejects **≤ 10% of good recordings** (`benchmark.target_false_reject_rate`),
then picks the gate that lets the **fewest bad recordings through** at that
rate. The held-out test set never sets the threshold. Whether the targets
(≤ 10% good rejected, ≤ 25% bad let through, both in `configs/component1.yaml`)
were met is reported under `targets` in `selected_gate_model.json`, for
cross-validation and for the test set. The winner and its threshold
(`gate_pass_probability` or `comp1a_pass_db`) are written to the config.

```
python -m component1_robustness.labels      # build results/component1_robustness/gate_labels.csv
python -m component1_robustness.benchmark   # tune thresholds, compare gates, write the winner + threshold to the config
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
| Voice presence | `test_voice_check.py`: the rule, plus **real labelled takes** — 6 with nobody speaking → `no_voice`, 3 of the user's real voice → PASS (`tests/data/`) |
| Known-answer synthetic signals | `test_degradation.py` (exact SNR ±0.01 dB, gain ±0.01 dB), `test_quality_metrics.py` (duration limits, 5% clipping, silence/tone voice activity, SNR ±2 dB) |
| Controlled degradation with known labels | `test_labels.py`, `test_gate_models.py` |
| Sanity rules | every gate model: clean → PASS, noise / silence / clipped / too short / too long → FAIL; score never rises with more noise |
| Preservation | `test_features_check.py`, `test_pipeline.py` (tight tolerance → raw audio forwarded) |
| Reproducibility by hash | same input twice → identical `report.json`, WAVs and PNGs; same seed → identical benchmark CSV |
| Golden regression set | `tests/golden/`: 7 seeded clips (clean, 20/5/0 dB noise, clipped, 2.9 s, 15.1 s) and their expected reports; `test_golden_set.py` re-runs them (decisions exact, floats within 1e-4 so the set passes on Windows and Linux) |
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
- **Absolute level is not portable across devices.** Recording level (dBFS) only
  chooses the *message* for a flat take (`no_voice` vs `low_snr`), never pass/fail: corpora recorded at different gain sit
  at different levels even when clean. Needs per-device calibration (Phase 2).
- **Thresholds come from one laptop mic.** The v1.5 contrast and level thresholds
  were set from 13 labelled takes on one device; recheck them on phones (Phase 2).
  Synthetic test clips must be shaped like real takes (quiet lead-in/tail,
  `conftest.as_take`): a perfectly steady tone with no start looks like hum.
- **Benchmark and robustness numbers predate v1.5.** They were measured with the
  SNR/HNR rule; re-run `labels` and `benchmark` (gate_labels.csv lacks the new
  `speech_band_contrast_db` column).
- **`noisereduce` removes sustained vowels.** Without a noise-only sample it
  takes the steady vowel for noise (keeps ~4–7% of its level on a synthetic
  test). The preservation check catches this and forwards the raw audio
  instead, but the default enhancement method should be chosen by the
  benchmark on real data.
- **Short dataset clips.** The AH vowel recordings are 1.7–5.5 s at 8 kHz; some
  are above the 5 s maximum. The benchmark switches the duration rule off
  (`benchmark.apply_duration_rule`) so it compares quality judgement only.
- **Sample rate for Component 2.** Audio is forwarded at 16 kHz. Component 2's
  zero-crossing features depend on sample rate; confirm the rate its model was
  trained on.
- **Placeholders still to calibrate:** `min_voice_activity_pct` and
  `feature_tolerances` and `ddk_feature_tolerances` in the config. Relative tolerances also break down for
  features near zero (e.g. jitter of a perfectly periodic signal).
- **Silence-based SNR on digitally silent pauses** reads low (~5 dB): all-zero
  frames are dropped before the noise floor is taken. Real recordings always
  have some background noise, so this mainly affects synthetic clips.
