# Parkinson Speech AI

**Language-independent voice screening for Parkinson's disease: a smartphone-based triage tool for Sri Lankan primary care.**

A screening/decision-support prototype, not a medical diagnosis tool. Three
independent components, designed to eventually fuse together:

```
PARTICIPANT → SMARTPHONE RECORDING
      → COMPONENT 1 (Audio Quality / Robustness Gate)
      → COMPONENT 2 ("aaaaaa" sustained vowel) + COMPONENT 3 ("pa-ta-ka" DDK)
      → FUSION → ML MODEL → PD SCREENING OUTPUT
```

**Phase 1 (current):** validate on public English / language-independent-task
datasets. **Phase 2 (planned):** collect original Sinhala recordings (sustained
vowel, DDK, reading) from PD patients and healthy controls in Sri Lanka, and
retrain/adapt this pipeline on them.

Once Phase 1 is validated, the plan is to package this as a **Flutter mobile
app** for use in Sri Lankan primary care clinics.

**New to this repo?** → **[SETUP.md](SETUP.md)** has environment setup, the
git branch workflow, and where to get the datasets. This README covers what
the project does and each component's results.

## Team

Three members, one component each. Work happens on `component/<name>`
branches off `main`.

## Components

| | Focus | Task | Code | Best result |
|---|---|---|---|---|
| **1** | Acoustic robustness + quality gate | Gate every recording before 2/3 | `component1_robustness/` | See below |
| **2** | Phonation | Sustained vowel "aaaaaa" | `src/component2_phonation/` | 81.0% CV accuracy |
| **3** | Speech-motor (DDK) | "pa"/"ta" repetition | `src/component3_ddk/` | 94.0% CV accuracy |

Each component's own README has full details, datasets used, caveats, and
exact commands to reproduce.

## Setup

Full instructions (venv, data, git workflow) are in **[SETUP.md](SETUP.md)**.
Quick version:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Component 2 — Phonation (4 baselines)

| Baseline | Data | Recordings/Participants | CV Accuracy |
|---|---|---|---|
| ReadText (stand-in) | MDVR-KCL | 37 / 37 | ~78% |
| Sustained vowel /a/ (own) | "AH" dataset | 80 / 80 | ~68% |
| Sustained vowel /a/ (Sakar et al. 2018, precomputed features) | UCI benchmark | 756 / 252 | ~80.5% (imbalanced) |
| **Sustained vowel /a/, combined raw audio** (AH + Italian PVS) | — | 179 / 126 | **81.0%, balanced** |

```
python -m src.component2_phonation.train_vowel_combined
python -m src.component2_phonation.predict path/to/recording.wav vowel_combined
```

## Component 3 — Speech-Motor / DDK

100 "pa"/"ta" recordings, 46 participants (Italian PVS dataset), properly
age-matched PD/HC groups. **94.0% CV accuracy (RF), 95% (SVM)** — the
strongest result in the project, though it needs replication before treating
94% as an expected real-world number (single dataset, modest sample size).

```
python -m src.component3_ddk.train
python -m src.component3_ddk.predict path/to/pa_or_ta_recording.wav
```

## Component 1 — Acoustic Robustness & Quality Gate

The first stage of the pipeline: a **quality gate** (not a PD classifier).
For each recording it checks duration, clipping and noise, tries enhancement,
checks that enhancement did not alter the PD biomarkers (jitter, shimmer, HNR,
F0), and either forwards the audio to Component 2/3 or asks the user to
re-record. Full details: [component1_robustness/README.md](component1_robustness/README.md).

**Robustness study** (synthetic degradations, Component 2's own model):
compression is well tolerated (96–100% prediction agreement with clean even at
low quality), but background noise and quiet/distant recording degrade it
sharply (~57–60% at 0 dB SNR or −12 dB gain). This is why the gate exists.

**Gate results.** The old validation labelled every clip in a degradation
condition the same way; the new benchmark labels each clip by what actually
happened to it and compares five gate models under participant-grouped
5-fold cross-validation with a held-out test set.

| Gate | Labels | Accuracy | Recall (unreliable) | False accept rate |
|---|---|---|---|---|
| comp1-A (SNR/HNR ≥ 10 dB), previous validation | per condition, 360 clips | 59.4% | 48.6% | 51.4% |
| comp1-A / B (RF, SVM, LogReg) / C (DNSMOS) | per clip, 81 clips × 12 conditions | *run the benchmark (below)* | | |

The new rows come from `results/component1_robustness/gate_benchmark.csv`
after running the two commands below on the AH vowel dataset (not in git; see
SETUP.md). The selected model and the reason are written to
`selected_gate_model.json` and to `gate_model` in `configs/component1.yaml`.

```
python -m component1_robustness.labels      # per-clip labels
python -m component1_robustness.benchmark   # compare gates, select one
python -m component1_robustness.cli --input recording.m4a --task vowel
pytest component1_robustness/tests          # full verification suite
```

## Known limitations (read before quoting any number externally)

- Component 2's vowel task carries no language content, so pooling
  English/Italian raw audio for it is defensible — this would NOT be valid
  for the ReadText or DDK tasks, which are content/language-dependent.
- Nothing here has cleared >90% under honest, participant-grouped
  cross-validation except Component 3's DDK baseline, which needs
  independent replication before being treated as a stable number.
- All datasets are public, existing (non-Sri-Lankan) sources. Phase 2's
  Sinhala data collection is the real test of whether any of this transfers.
- See `src/component2_phonation/README.md` for a documented bug (and fix) in
  participant-ID parsing that was silently coarsening cross-validation groups
  — worth knowing about before trusting a similar loader written for new data.
