# Sakar et al. (2018) Parkinson's Disease Classification dataset

Source: UCI Machine Learning Repository, "Parkinson's Disease Classification"
(Sakar et al., 2018 — sustained vowel /a/, recorded at Istanbul University).

`pd_speech_features.csv` — **precomputed features only, no raw audio.**

- 756 rows = 252 participants x 3 recordings each
- 752 acoustic feature columns (jitter/shimmer variants, PPE, DFA, RPDE, MFCCs,
  TQWT wavelet-transform features, ...)
- `class`: 1 = PD (188 participants), 0 = HC (64 participants) — **imbalanced, ~3:1**
- Row 0 of the raw CSV is a "Baseline Features" section label, not data — load
  with `header=1` (handled by `src/component2_phonation/sakar_dataset.py`)

**Caveats:**
- No raw audio means `features.py` (our own extractor) can't be applied here —
  this is a separate, standalone baseline on the dataset's own features.
- 3 recordings per participant — CV must group by `id`/`participant_id` or you
  leak the same person across train/test. `train_sakar.py` does this correctly.
- Class imbalance (564 PD rows vs 192 HC rows) means raw accuracy is a weak
  metric on its own — a trivial "always predict PD" baseline already scores
  ~74.6%. Check precision/recall/F1 per class, not just accuracy.
