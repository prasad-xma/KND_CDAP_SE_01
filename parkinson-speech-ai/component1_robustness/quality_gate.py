"""The reliability-flagging classifier from the proposal (slide 12/16/17):
"reliable -> pass to Components 2/3" vs "unreliable -> flag / re-record".

Not a trained ML classifier — this is a threshold rule over a blind quality
estimate, and the threshold is not arbitrary: it's read directly off our own
`experiment.py` robustness study (results/component1_robustness/
robustness_summary.csv). That study found Component 2's prediction agreement
with clean audio stays high (0.80-1.0) at 10dB injected SNR and above, then
collapses sharply below it (0.64 at 5dB, 0.59 at 0dB). 10dB is therefore
where this project's own evidence says a recording stops being trustworthy.

The measurements themselves (silence-based SNR, HNR, level, ...) live in
`quality_metrics.py`; see its docstring for why two estimators are used.
Verified against synthetic noise injection: clean recordings measure
~11-23dB HNR; injecting the same 10dB SNR noise that the robustness study
flags as the accuracy cliff drops HNR to ~9dB — so the same 10dB threshold
applies to either estimator.

A third, INFORMATIONAL-ONLY check: absolute recording level (mean RMS in
dBFS), reported but NOT used to gate pass/fail by default. `validate_
quality_gate.py` found SNR/HNR alone is blind to pure gain reduction (a
quiet/distant recording) — a quieter copy of the same clean audio has an
unchanged noise-to-signal *ratio*, so it still reads as "reliable" even
though the robustness study shows Component 2's predictions do degrade on
quiet/far recordings. A fixed dBFS floor looked like the fix, calibrated
from the AH dataset's clean recordings (~-10 to -16 dBFS) — but checking it
against the Italian PVS corpus (the DDK model's own training data) showed
96% of those recordings sit below that floor despite being valid clean data;
that corpus was just captured at lower gain. Absolute level isn't portable
across recording setups/microphones without a per-device calibration this
project doesn't have yet, so it stays informational rather than blocking —
documented here as a known limitation and a concrete next step (Phase 2:
calibrate per-device, or normalize against a reference tone) rather than
quietly worked around.
"""

from dataclasses import dataclass

import librosa

from common.audio_io import ensure_wav
from component1_robustness.quality_metrics import (  # noqa: F401  (re-exported for old callers)
    estimate_quality_db,
    mean_level_dbfs,
)

RELIABLE_DB = 10.0  # from robustness_summary.csv — see module docstring
MIN_LEVEL_DBFS = -18.0  # from this project's own clean-recording level distribution — see module docstring


@dataclass
class QualityGateResult:
    passed: bool
    estimated_snr_db: float
    method: str
    level_dbfs: float
    message: str


def check_quality(audio_path, reliable_db=RELIABLE_DB, min_level_dbfs=None):
    """Run the quality gate on a recording. Returns a QualityGateResult.

    Pass/fail is decided by the SNR/HNR estimate alone by default. `level_dbfs`
    is always computed and returned for visibility, but does NOT affect
    `passed` unless you explicitly opt in with `min_level_dbfs=...` — see the
    module docstring for why it's not a safe default (it doesn't generalise
    across different recording corpora/devices without per-device
    calibration this project doesn't have yet).
    """
    wav_path = ensure_wav(audio_path)
    y, sr = librosa.load(wav_path, sr=None, mono=True)

    estimate_db, method = estimate_quality_db(wav_path)
    level_dbfs = mean_level_dbfs(y)

    quality_ok = estimate_db >= reliable_db
    level_ok = min_level_dbfs is None or level_dbfs >= min_level_dbfs
    passed = quality_ok and level_ok

    label = "estimated SNR" if method == "silence_snr" else "HNR (no silence detected, using harmonics-to-noise ratio)"
    if passed:
        message = (
            f"Reliable ({label} {estimate_db:.1f} dB, level {level_dbfs:.1f} dBFS) "
            "— passed to Components 2/3."
        )
    elif not level_ok:
        message = (
            f"Unreliable (recording level {level_dbfs:.1f} dBFS, below the {min_level_dbfs:.0f} dBFS "
            "floor) — too quiet/far from the microphone. Please re-record closer to the microphone."
        )
    else:
        message = (
            f"Unreliable ({label} {estimate_db:.1f} dB, below the {reliable_db:.0f} dB "
            "threshold) — please re-record in a quieter environment, closer to the microphone."
        )

    return QualityGateResult(
        passed=passed, estimated_snr_db=estimate_db, method=method, level_dbfs=level_dbfs, message=message
    )
