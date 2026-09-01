# Component 2 — Phonation-Based Parkinson's Detection

Three baselines. The first two share our own feature extractor and CV/training
code; the third (Sakar et al.) is precomputed-features-only but reuses the same
CV/training code.

| Task | Data | Recordings | Participants | CV accuracy (RF) |
|---|---|---|---|---|
| ReadText (stand-in) | MDVR-KCL `ReadText` | 37 | 37 (16 PD / 21 HC) | ~78% |
| Sustained vowel /a/ (own extraction) | `data/vowel_task/` ("AH") | 80 | 80 (40 PD / 40 HC) | ~68% |
| Sustained vowel /a/ (Sakar et al. 2018) | `data/sakar_pd_dataset/` | 756 | 252 (188 PD / 64 HC) | ~80.5% RF / ~82% SVM |
| Sustained vowel /a/, **combined raw audio** (AH + Italian PVS) | `train_vowel_combined.py` | 179 | 126 (95 PD / 84 HC) | ~81.0%, balanced precision/recall |

The Sakar dataset is by far the strongest baseline here — much larger, and it's
a widely-used published benchmark — but read the class-imbalance caveat below
before quoting its accuracy number on its own.

- `features.py` — the ONE feature-extraction function (`extract_phonation_features`),
  used identically for training and prediction, for both tasks. Do not duplicate this
  logic elsewhere — the original Colab notebook computed jitter/shimmer/HNR differently
  at prediction time than at training time, which silently broke real-world predictions.
- `dataset.py` / `vowel_dataset.py` — dataset-specific loaders (extraction + label
  matching); both call `extract_phonation_features` and produce the same column schema.
- `../common/model_evaluation.py` — shared participant-grouped 5-fold CV (RF / SVM /
  Logistic Regression), final-model fit, plots, and `metrics.json`, used by every
  `train*.py` script in this component AND by Component 3's `train.py`.
- `train.py` — ReadText baseline. Saves `models/component2_phonation_readtext_rf.joblib`
  and `results/component2_phonation/readtext_*`.
- `train_vowel.py` — sustained-vowel /a/ baseline (own extraction). Saves
  `models/component2_phonation_vowel_rf.joblib` and `results/component2_phonation/vowel_*`.
- `sakar_dataset.py` / `train_sakar.py` (+ `train_sakar_tuned.py`) — Sakar et al. baseline
  (precomputed features, no raw audio). Saves `models/component2_phonation_sakar_rf.joblib`
  and `results/component2_phonation/sakar_*`.
- `italian_pvs_dataset.py` — loader for the Italian Parkinson's Voice and Speech dataset's
  vowel-/a/ task (raw audio, `data/italian_pvs/`), reusing `extract_phonation_features`.
- `train_vowel_combined.py` — merges the AH dataset + Italian PVS vowel recordings into
  one feature table (valid because both are raw audio through the same extractor, and the
  vowel task carries no language content) and runs the shared baseline on it. Saves
  `models/component2_phonation_vowel_combined_rf.joblib` and
  `results/component2_phonation/vowel_combined_*`.
- `predict.py` — loads a saved model and predicts on one new `.wav` file (only works
  for the `readtext`/`vowel` models — the Sakar model can't be used on raw audio since
  it was trained on a different, precomputed feature set it can't reproduce from a wav).

Run from the `parkinson-speech-ai/` directory (with `.venv` set up per
`requirements.txt`):

```
python -m src.component2_phonation.train
python -m src.component2_phonation.train_vowel
python -m src.component2_phonation.train_sakar
python -m src.component2_phonation.predict path/to/recording.wav readtext
python -m src.component2_phonation.predict path/to/recording.wav vowel
```

## Notes / caveats

- **ReadText is a stand-in, not the real task.** MDVR-KCL has no sustained-vowel
  recording; `ReadText` was used to match the project's original preliminary-experiment
  writeup. The vowel-task baseline above (`vowel_task/`) is the actual "aaaaaa"-style
  design Component 2 is meant to test.
- **Vowel-task PD/HC groups are not age-matched** (PD mean age 67.0 vs HC mean age 47.6).
  Any accuracy from this baseline may partly reflect age-related voice change rather
  than PD-specific pathology — call this out if reporting this number. Feature
  importances (jitter, std_f0, std_rms) are at least consistent with known PD phonation
  biomarkers rather than an obviously age/ZCR-driven shortcut, but this is not proof
  against the confound.
- Vowel-task audio is 8kHz mono (phone-call quality), lower than typical lab recordings
  — expect this to cap HNR/formant-based feature reliability somewhat.
- Lower vowel-task accuracy (~68%) vs ReadText (~78%) is plausible given: fewer frames
  of signal per recording, single vowel vs. continuous speech, lower sample rate, and
  the smaller/noisier telephone-quality source — not necessarily evidence that sustained
  vowels are a worse biomarker in general.
- **Sakar et al. dataset is class-imbalanced (564 PD rows vs 192 HC rows, ~3:1).** A
  trivial "always predict PD" model already scores ~74.6% accuracy, so the ~80.5%
  headline RF number is a smaller real improvement than it looks. HC recall in
  particular is weak (~51%) even with `class_weight="balanced"` — report macro-F1 or
  per-class precision/recall alongside accuracy, not accuracy alone, if this baseline
  is used in the writeup. `results/component2_phonation/sakar_metrics.json` has the
  full breakdown.
- **Combined AH + Italian PVS is the most methodologically honest vowel-task baseline so
  far, and now the best**: 126 participants, near-balanced classes (95 PD / 84 HC, vs.
  Sakar's 3:1 imbalance), and the Italian half is properly age-matched (HC mean 49.9 vs
  PD mean 50.0 — contrast with the AH dataset's own 47.6 vs 67.0 mismatch). **81.0%
  accuracy**, beating Sakar's 80.5% while keeping balanced HC/PD recall (82.1%/80.0%
  vs. Sakar's lopsided 51%/91%), and reflecting real generalization across two
  countries/devices/recording protocols — a harder, more meaningful test than a
  single-site number.
- **Real bug caught and fixed**: `italian_pvs_dataset.py` initially derived each
  recording's participant folder as `path.split(os.sep)[1]`, which is correct for the
  Elderly HC group's flat layout but wrong for the PD group, whose folder structure has
  an extra numbered subfolder (`1-5`, `6-10`, `11-16`, `17-28`) between the group and the
  person — so several different real people were silently merged into one fake
  "participant" for CV grouping (26 fake groups instead of the true ~50 people; combined
  dataset reported 106 participants instead of 126). Fixed by taking the person folder as
  `path.split(os.sep)[-2]` (always the folder directly containing the file, regardless of
  nesting depth) instead of a fixed index. Accuracy actually went up after the fix
  (77.1% → 81.0%) because CV folds are no longer artificially coarse-grained.
- Sakar et al. is precomputed-features-only (no raw audio), so it cannot be merged with
  the `vowel_task`/`ReadText` feature tables (different, incompatible feature sets) — it
  stands as an independent, much larger literature-benchmark baseline rather than more
  training data for the same model.
- **Tried to push Sakar accuracy higher via `train_sakar_tuned.py`** (SelectKBest feature
  selection + RandomizedSearchCV over RF / SVM / HistGradientBoosting, class-imbalance
  aware). Result: best CV accuracy 80.4%, balanced accuracy 71.8%, HC recall 54.2% —
  essentially the same as the untuned RF baseline. This is a genuine ceiling with proper
  participant-grouped CV, not a tuning gap: the original Sakar et al. paper itself reports
  similar mid-80s% at best with careful feature selection. Treat ~80-85% as the honest
  range for this dataset/task; a claimed 90%+ on it should be treated with suspicion
  (almost always means CV wasn't grouped by participant, so the same person's 3 recordings
  leaked across train/test).
