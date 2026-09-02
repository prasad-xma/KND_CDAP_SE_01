# Setup Guide (for team members)

This gets you from a fresh clone to running any of the 3 components locally.
If you just want to know *what* the project does, read [README.md](README.md)
first — this file is only the "how do I get it running" part.

## Prerequisites

- **Git**
- **Python 3.10+** (developed/tested on 3.12)
- No system-wide **ffmpeg** install needed — it's pulled in automatically via
  the `imageio-ffmpeg` pip package and used to handle `.m4a`/`.mp3` recordings.

## 1. Clone and pick your branch

```
git clone https://github.com/prasad-xma/KND_CDAP_SE_01.git
cd KND_CDAP_SE_01/parkinson-speech-ai
```

Each member works on their own branch off `main`, named `component/<your-name>`
(e.g. `component/matheesha`). If you don't have one yet:

```
git checkout main
git pull
git checkout -b component/<your-name>
```

Merge into `main` via a pull request when a component is ready to share —
don't commit straight to `main`.

## 2. Python environment

From inside `parkinson-speech-ai/`:

```
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Always run commands from `parkinson-speech-ai/` (not the repo root) — the code
is invoked as a module, e.g. `python -m src.component2_phonation.train`, which
only resolves correctly from this directory.

**Windows note:** `pesq` (in requirements.txt, used only by
`evaluate_enhancement.py` for one optional quality metric) needs a C compiler
to build and will fail on plain Windows without Visual C++ Build Tools. If it
fails, either install "Microsoft C++ Build Tools" or just remove `pesq` from
your local install — everything else works without it. It installs cleanly
on Colab/Linux with no extra setup.

## 3. Project layout

```
parkinson-speech-ai/
  src/                    Python source, one folder per component
    common/               shared helpers (audio loading, model evaluation)
    component1_robustness/
    component2_phonation/
    component3_ddk/
    fusion/                Component 3's fusion ablation (vowel+DDK -> Score A+B)
    screening/              end-to-end pipeline: quality gate -> Score A/B -> fused PD Screening Score
  notebooks/colab_pipeline.ipynb          runs the whole pipeline on Colab
  data/                   datasets (see "Getting the data" below)
  models/                 pretrained .joblib models — already committed, ready to use
  notebooks/              exploratory / baseline notebooks
  results/                metrics, confusion matrices, feature-importance plots
  docs/                   presentation/planning docs
```

Each `src/component*/README.md` has the full detail for that component
(dataset specifics, known caveats, exact commands).

## 4. Getting the data

Not all data lives in git — some source archives are intentionally excluded
(GitHub hard-rejects files over 100MB, and these are ~500MB+):

| In git already | Not in git — ask a teammate or re-download |
|---|---|
| `data/sakar_pd_dataset/pd_speech_features.csv` | `data/26_29_09_2017_KCL.zip` (MDVR-KCL dataset, ~580MB) |
| `data/vowel_task/23849127.zip` ("AH" vowel dataset) | `data/italian_pvs/italian_pvs.zip` (Italian PVS dataset, ~570MB) |
| `data/test_audio/` (sample recordings) | |

If you're working on Component 2 or 3 and need the large archives, ask
Matheesha for a copy rather than re-downloading from scratch — saves you
tracking down the exact source version used.

`data/*/raw/` folders are **not** committed either — they're extracted
automatically the first time a training script runs (e.g.
`ensure_extracted()` in `vowel_dataset.py`). Don't commit anything under a
`raw/` folder; `.gitignore` already excludes it.

## 5. Pretrained models

`models/*.joblib` are already committed, so you can run predictions
immediately without training anything first:

```
python -m src.component2_phonation.predict path\to\recording.wav vowel_combined
python -m src.component3_ddk.predict path\to\pa_or_ta_recording.wav
```

Only retrain (`train*.py` scripts) if you're changing features/data for your
component — see each component's README for the exact command.

## 6. Running each component

| Component | Command |
|---|---|
| 1 — Robustness | `python -m src.component1_robustness.experiment` |
| 1 — Enhancement + quality gate | `python -m src.component1_robustness.evaluate_enhancement` |
| 1 — Quality gate precision/recall | `python -m src.component1_robustness.validate_quality_gate` |
| 2 — Phonation | `python -m src.component2_phonation.train_vowel_combined` |
| 3 — DDK | `python -m src.component3_ddk.train` |
| 3 — Fusion ablation | `python -m src.fusion.train_italian_pvs_fusion` |
| Final Score — end-to-end | `python -m src.screening.predict_screening path\to\vowel.wav path\to\ddk.wav` |

`evaluate_enhancement.py` and `train_italian_pvs_fusion.py` both need
`data/italian_pvs/italian_pvs.zip` (see "Getting the data" above) —
`train_italian_pvs_fusion.py` also needs
`results/component2_phonation/italian_pvs_vowel_features.csv` and
`results/component3_ddk/italian_pvs_ddk_features.csv`, which are produced by
running Component 2's and Component 3's own training scripts first.

## Common gotchas

- The repo path on Windows may contain spaces (e.g. under "4th year") — quote
  paths in commands.
- If `pip install` fails on `praat-parselmouth`, make sure you're on a
  64-bit Python 3.10+ interpreter — no prebuilt wheel exists for some
  older/32-bit setups.
- Component 2 had a real bug in participant-ID parsing that silently
  coarsened cross-validation groups (fixed, but documented in
  `src/component2_phonation/README.md`) — worth reading before writing a
  similar loader for new data.

## Stuck?

Ping Matheesha (component 2 + repo setup) or check the relevant component's
own README first — most dataset quirks and caveats are documented there.
