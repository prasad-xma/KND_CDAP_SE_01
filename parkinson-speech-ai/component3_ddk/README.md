# Component 3 — Speech-Motor Detection (DDK)

Diadochokinetic ("pa"/"ta" repetition) baseline. Data: Italian Parkinson's
Voice and Speech dataset (`data/italian_pvs/`, shared with Component 2 — same
zip, different task codes: D1 = "pa" x5sec, D2 = "ta" x5sec).

- `features.py` — `extract_ddk_features`: syllable rate, inter-onset-interval
  mean/std/CV (rhythm regularity), pause count/ratio, spectral
  centroid/bandwidth, and 3 MFCC coefficients. One function, used identically
  for training and prediction (same discipline as Component 2's `features.py`
  — see that component's README for why this matters).
- `italian_ddk_dataset.py` — extracts D1/D2 files from the zip and builds the
  feature table. **Important quirk**: the PD group's folder layout has an
  extra numbered subfolder (`1-5`, `6-10`, `11-16`, `17-28`) between the group
  and the per-person folder that the Elderly HC group doesn't have — the
  person folder is always `parts[-2]` of the relative path, never `parts[1]`.
  Getting this wrong silently merges several different people into one fake
  "participant" for CV grouping (caught and fixed during development — see
  git history / project memory).
- `train.py` — participant-grouped 5-fold CV (RF/SVM/LogReg via
  `src/common/model_evaluation.py`), saves
  `models/component3_ddk_ddk_rf.joblib` and `results/component3_ddk/ddk_*`.
- `predict.py` — loads the saved model and predicts on one new "pa"/"ta" `.wav`.

```
python -m src.component3_ddk.train
python -m src.component3_ddk.predict path/to/pa_or_ta_recording.wav
```

## Result

100 recordings (50 "pa" + 50 "ta"), 46 unique participants (22 HC / 24 PD —
a few PD recordings dropped for too few detected syllable onsets), balanced
classes. **94.0% CV accuracy (Random Forest), 95% (SVM)**, precision/recall
balanced across HC/PD (~91-96% each). This is the strongest result across
the whole project.

**Read before quoting this number:** DDK/articulation timing is a
well-documented strong PD signal in the literature (motor symptoms directly
affect speech timing), so a high number here is plausible — but this is a
single dataset, 46 participants, 12 hand-designed features, one train/test
protocol. Treat as a promising phase-1 result that needs replication (e.g.
against Sakar-style DDK data, or the planned Sinhala DDK collection) before
treating 94% as an expected real-world number.
