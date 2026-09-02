"""End-to-end screening pipeline — implements the "Our Solution" diagram from
the proposal (slide 5) as actual code for the first time:

    Patient ("aaaaaa" + "pa-ta-ka")
        -> Stage 2: Component 1 Audio Quality Gate
        -> Stage 3: Component 2 (Phonation AI, Score A) + Component 3 (Speech-Motor AI, Score B)
        -> Stage 4: Fusion (Score A + Score B)
        -> Stage 5: PD Screening Score + decision-support message

Uses each component's own headline production model (vowel_combined_rf —
Component 2's best-reported 81% baseline — and ddk_rf — Component 3's 94%
baseline), not the smaller Italian-PVS-only fusion bundle from
`src/fusion/train_italian_pvs_fusion.py`. That bundle exists to answer "does
fusion beat either alone?" on a matched 46-participant sample; it is not
trained on enough data to be the production Score A/B — the two components'
own broader-trained production models are.

Fusion is a plain average of Score A and Score B ("Score A + B" per slide 26/
31), matching the unweighted decision-level strategy the ablation study found
performs at least as well as feature-level/stacked fusion — with no extra
meta-learner dependency to keep track of.

IMPORTANT: this is a decision-support screening output, not a diagnosis (see
slide 5's own disclaimer) — never present it as one.

Usage:
    python -m src.screening.predict_screening path/to/vowel.wav path/to/ddk.wav
"""

import os
import sys
import json
from dataclasses import dataclass, asdict

import joblib
import pandas as pd

from ..component1_robustness.quality_gate import check_quality
from ..component2_phonation.features import extract_phonation_features
from ..component3_ddk.features import extract_ddk_features

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS_DIR = os.path.join(REPO_ROOT, "models")
VOWEL_MODEL_PATH = os.path.join(MODELS_DIR, "component2_phonation_vowel_combined_rf.joblib")
DDK_MODEL_PATH = os.path.join(MODELS_DIR, "component3_ddk_ddk_rf.joblib")

PD_SCORE_THRESHOLD = 0.5

DECISION_SUPPORT_DISCLAIMER = (
    "Decision-Support Output — Not a Diagnosis. "
    "Flags likely PD cases for primary-care referral to a neurologist."
)


@dataclass
class ScreeningResult:
    stage_reached: str
    quality_gate_vowel: dict
    quality_gate_ddk: dict
    score_a_phonation: float = None
    score_b_speech_motor: float = None
    fused_score: float = None
    classification: str = None
    message: str = None

    def to_json(self):
        return json.dumps(asdict(self), indent=2)


def _load_models():
    vowel_bundle = joblib.load(VOWEL_MODEL_PATH)
    ddk_bundle = joblib.load(DDK_MODEL_PATH)
    return vowel_bundle, ddk_bundle


def run_screening(vowel_wav_path, ddk_wav_path):
    """Run the full pipeline on one patient's two recordings and return a ScreeningResult."""
    gate_vowel = check_quality(vowel_wav_path)
    gate_ddk = check_quality(ddk_wav_path)

    result = ScreeningResult(
        stage_reached="quality_gate",
        quality_gate_vowel=asdict(gate_vowel),
        quality_gate_ddk=asdict(gate_ddk),
    )

    if not gate_vowel.passed or not gate_ddk.passed:
        failed = []
        if not gate_vowel.passed:
            failed.append("sustained vowel ('aaaaaa')")
        if not gate_ddk.passed:
            failed.append("DDK ('pa-ta-ka')")
        result.message = (
            f"Recording(s) flagged unreliable by the quality gate: {', '.join(failed)}. "
            "Please re-record in a quieter environment, closer to the microphone, "
            "before a screening score can be produced."
        )
        return result

    vowel_bundle, ddk_bundle = _load_models()

    vowel_feats = extract_phonation_features(vowel_wav_path)
    ddk_feats = extract_ddk_features(ddk_wav_path)

    if vowel_feats is None or ddk_feats is None:
        result.stage_reached = "feature_extraction_failed"
        missing = []
        if vowel_feats is None:
            missing.append("sustained vowel (no voiced frames detected)")
        if ddk_feats is None:
            missing.append("DDK (too few syllable onsets detected)")
        result.message = f"Could not extract features from: {', '.join(missing)}. Please re-record."
        return result

    vowel_X = pd.DataFrame([vowel_feats])[vowel_bundle["feature_names"]]
    ddk_X = pd.DataFrame([ddk_feats])[ddk_bundle["feature_names"]]

    score_a = float(vowel_bundle["model"].predict_proba(vowel_X)[0][1])
    score_b = float(ddk_bundle["model"].predict_proba(ddk_X)[0][1])
    fused_score = (score_a + score_b) / 2

    result.stage_reached = "complete"
    result.score_a_phonation = round(score_a, 4)
    result.score_b_speech_motor = round(score_b, 4)
    result.fused_score = round(fused_score, 4)
    result.classification = "Likely PD" if fused_score >= PD_SCORE_THRESHOLD else "Likely Healthy"
    result.message = DECISION_SUPPORT_DISCLAIMER
    return result


def print_report(vowel_wav_path, ddk_wav_path, result):
    """Pretty-print a screening report — designed to be screenshot-friendly."""
    print("=" * 60)
    print("  PARKINSON'S DISEASE VOICE SCREENING — REPORT")
    print("=" * 60)
    print(f"  Vowel recording : {os.path.basename(vowel_wav_path)}")
    print(f"  DDK recording   : {os.path.basename(ddk_wav_path)}")
    print("-" * 60)
    print("  STAGE 2 — Component 1: Audio Quality Gate")
    print(f"    Vowel: {result.quality_gate_vowel['message']}")
    print(f"    DDK  : {result.quality_gate_ddk['message']}")
    print("-" * 60)

    if result.stage_reached != "complete":
        print(f"  STOPPED at stage: {result.stage_reached}")
        print(f"  {result.message}")
        print("=" * 60)
        return

    print("  STAGE 3 — Parallel AI Components")
    print(f"    Score A (Component 2, Phonation)     : {result.score_a_phonation:.1%} PD probability")
    print(f"    Score B (Component 3, Speech-Motor)   : {result.score_b_speech_motor:.1%} PD probability")
    print("-" * 60)
    print("  STAGE 4 — Fusion (Score A + Score B)")
    print(f"    Fused PD Screening Score              : {result.fused_score:.1%}")
    print("-" * 60)
    print("  STAGE 5 — Output")
    print(f"    Classification: {result.classification}")
    print(f"    {result.message}")
    print("=" * 60)


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m src.screening.predict_screening <vowel.wav> <ddk.wav>")
        sys.exit(1)

    vowel_wav_path, ddk_wav_path = sys.argv[1], sys.argv[2]
    result = run_screening(vowel_wav_path, ddk_wav_path)
    print_report(vowel_wav_path, ddk_wav_path, result)


if __name__ == "__main__":
    main()
