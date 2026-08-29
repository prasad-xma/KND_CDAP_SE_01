# Vowel-task dataset (sustained /a/, "AH")

Zip: `23849127.zip` — contains:
- `Demographics_age_sex.xlsx` (sheet "Parselmouth": Sample ID, Label, Age, Sex)
- `PD_AH.zip` → `PD_AH/*.wav` (40 recordings, label "PwPD")
- `HC_AH.zip` → `HC_AH/*.wav` (41 recordings, label "HC")

8kHz mono wav, 1.7–5.5s each. Each wav's filename (minus `.wav`) matches a
`Sample ID` row in the demographics sheet exactly — that's how labels/age/sex
are attached (see `src/component2_phonation/vowel_dataset.py`).

`raw/` (gitignored) is the extracted contents, created automatically by
`ensure_extracted()` the first time `train_vowel.py` runs.

**Known caveat:** PD (mean age 67.0) and HC (mean age 47.6) groups are not
age-matched. Report accuracy on this baseline with that caveat — some of the
signal may be age-related voice change rather than PD-specific.
