"""Task check: did the user actually do the task, or just make some sound?

Why this exists: the quality gate judges HOW WELL a take was recorded, not WHAT
was said. Clear gibberish is a good-quality recording, so it passed (real app
take, 2026-10-28). Component 2 needs one steady "aaaa"; anything else gives it
features it was never trained on.

Vowel rule (config task_check.vowel), on the RAW audio, Praat pitch track
(10 ms frames, 70-400 Hz, gaps <= 0.10 s bridged):
    longest_voiced_s >= min_longest_voiced_s   one unbroken voiced stretch, i.e. a held vowel
    voiced_share     >= min_voiced_share       that stretch is most of the voicing in the take
    otherwise FAIL "wrong_task" ("say one steady 'aaaa'").
pitch_spread_semitones is recorded for information only: inside the longest stretch
it did not separate gibberish from real vowels (gibberish 3.5, real dataset vowels
up to 6.6 semitones), so it is not used to reject.

Calibration (scratch analysis, 2026-10-28):
    81 real sustained vowels (AH dataset, PD + HC): longest 1.31-7.16 s, share 0.58-1.00
        -> 0 of 81 rejected by the thresholds below
    user's real app takes (3): longest 1.84-3.47 s, share 0.98-1.00 -> pass
    user's doubtful take (1, not sure if gibberish): 1.48 s, share 0.90 -> pass
    user's gibberish take (1): longest 0.33 s, share 0.28 -> wrong_task
Thresholds sit below every real vowel, matching the gate's priority that good
recordings must pass. PLACEHOLDERS until more labelled wrong-task takes exist.

Silence is NOT this check's job: room hum can look voiced for 1-3 s. The voice
check (voice_check.py) catches silent takes first.

DDK ("pa-ta-ka") has no task check yet (syllable rate did not separate gibberish
from real DDK); it is reported as not checked and always passes.
"""

import numpy as np
import parselmouth

# Same pitch range as Component 2, taken from its feature extractor (one source of truth).
from component2_phonation.features import F0_MAX_HZ, F0_MIN_HZ

TIME_STEP_S = 0.01
MAX_GAP_S = 0.10          # short voicing dropouts inside one held vowel are bridged

DEFAULT_VOWEL_CHECK = {
    "min_longest_voiced_s": 1.0,
    "min_voiced_share": 0.5,
}


def task_check_config(config: dict) -> dict | None:
    """config["task_check"] with vowel defaults filled in; None when absent or disabled."""
    section = config.get("task_check")
    if not section or not section.get("enabled", False):
        return None
    return {**section, "vowel": {**DEFAULT_VOWEL_CHECK, **(section.get("vowel") or {})}}


def voiced_runs(f0: np.ndarray, time_step: float = TIME_STEP_S, max_gap_s: float = MAX_GAP_S) -> list[tuple[int, int]]:
    """(first, last) frame index of each voiced run (f0 > 0); gaps <= max_gap_s are bridged."""
    max_gap = int(round(max_gap_s / time_step))
    runs, start, last, gap = [], None, None, 0
    for i, voiced in enumerate(np.asarray(f0) > 0):
        if voiced:
            if start is None:
                start = i
            last, gap = i, 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                runs.append((start, last))
                start = None
    if start is not None:
        runs.append((start, last))
    return runs


def pitch_track(y: np.ndarray, sr: int) -> np.ndarray:
    """Praat F0 per 10 ms frame (0 = unvoiced). Also used by enhancement.noise_reference()."""
    sound = parselmouth.Sound(np.asarray(y, dtype=np.float64), sampling_frequency=sr)
    return sound.to_pitch(time_step=TIME_STEP_S, pitch_floor=F0_MIN_HZ,
                          pitch_ceiling=F0_MAX_HZ).selected_array["frequency"]


def vowel_task_metrics(y: np.ndarray, sr: int) -> dict:
    """Longest unbroken voiced stretch, its share of all voicing, and its pitch spread."""
    f0 = pitch_track(y, sr)
    runs = voiced_runs(f0)
    if not runs:
        return {"longest_voiced_s": 0.0, "voiced_share": 0.0, "n_voiced_runs": 0,
                "pitch_spread_semitones": None}
    lengths = [(b - a + 1) * TIME_STEP_S for a, b in runs]
    a, b = runs[int(np.argmax(lengths))]
    segment = f0[a:b + 1]
    segment = segment[segment > 0]
    semitones = 12.0 * np.log2(segment / np.median(segment))
    return {
        "longest_voiced_s": float(max(lengths)),
        "voiced_share": float(max(lengths) / sum(lengths)),
        "n_voiced_runs": len(runs),
        "pitch_spread_semitones": float(np.std(semitones)),
    }


def check_task(y_raw: np.ndarray, sr: int, task: str, config: dict) -> dict | None:
    """Task check for one take. None when task_check is disabled in the config.

    Returns the measured values, the thresholds, "checked", "passed" and
    "fail_reason" ("wrong_task" when not passed, else None).
    """
    c = task_check_config(config)
    if c is None:
        return None
    if task != "vowel":
        return {"task": task, "checked": False, "passed": True, "fail_reason": None}
    thresholds = c["vowel"]
    metrics = vowel_task_metrics(y_raw, sr)
    passed = (metrics["longest_voiced_s"] >= thresholds["min_longest_voiced_s"]
              and metrics["voiced_share"] >= thresholds["min_voiced_share"])
    return {
        "task": task,
        "checked": True,
        **metrics,
        "min_longest_voiced_s": float(thresholds["min_longest_voiced_s"]),
        "min_voiced_share": float(thresholds["min_voiced_share"]),
        "passed": bool(passed),
        "fail_reason": None if passed else "wrong_task",
    }
