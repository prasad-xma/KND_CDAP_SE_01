"""Golden regression set: rerun run_gate on 7 stored clips and compare to stored reports.

A failure here means the pipeline's output changed. If the change is intended,
regenerate (python component1_robustness/tests/golden/generate.py) and review
the diff of golden/expected/*.json before committing.
"""

import io
import json
import math

import pytest
import soundfile as sf

from component1_robustness.pipeline import run_gate
from golden.generate import CLIPS_DIR, EXPECTED_DIR, SR, TASK, golden_config, make_clips, normalise

# Relative/absolute float tolerance. MFCC means are float32 and differ by ~3e-6 (relative)
# between Windows and Linux builds of the same libraries, so 1e-6 was too strict across
# machines. 1e-4 still catches any real behaviour change (decisions, reasons and paths are
# compared exactly; a 0.1% change in any number fails).
FLOAT_TOL = 1e-4

# What each clip MEANS. Checked separately so a regenerated set cannot silently change it.
EXPECTED_DECISIONS = {
    "clean_5s": ("PASS", "ok"),
    "noise_20db": ("PASS", "ok"),
    "noise_5db": ("FAIL", "low_snr"),
    "noise_0db": ("FAIL", "low_snr"),
    "clipped": ("FAIL", "clipped"),
    "short_2p9s": ("FAIL", "too_short"),
    "long_15p1s": ("FAIL", "too_long"),
}


def assert_matches(actual, expected, path: str = "report") -> None:
    """Same structure and values; floats equal within FLOAT_TOL (absolute or relative)."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected an object"
        assert actual.keys() == expected.keys(), f"{path}: keys differ: {set(actual) ^ set(expected)}"
        for key in expected:
            assert_matches(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, float) or (isinstance(actual, float) and isinstance(expected, int)):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), f"{path}: not a number"
        assert math.isclose(actual, expected, rel_tol=FLOAT_TOL, abs_tol=FLOAT_TOL), \
            f"{path}: {actual!r} != {expected!r}"
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"


@pytest.mark.parametrize("name", EXPECTED_DECISIONS)
def test_report_matches_golden(name, tmp_path):
    expected = json.loads((EXPECTED_DIR / f"{name}.json").read_text(encoding="utf-8"))
    report = normalise(run_gate(CLIPS_DIR / f"{name}.wav", TASK, golden_config(tmp_path)), tmp_path)
    assert_matches(report, expected)


@pytest.mark.parametrize("name,decision_reason", EXPECTED_DECISIONS.items())
def test_golden_decisions_mean_what_they_say(name, decision_reason):
    expected = json.loads((EXPECTED_DIR / f"{name}.json").read_text(encoding="utf-8"))
    assert (expected["decision"], expected["reason"]) == decision_reason


def test_golden_set_is_complete():
    assert {p.stem for p in CLIPS_DIR.glob("*.wav")} == set(EXPECTED_DECISIONS)
    assert {p.stem for p in EXPECTED_DIR.glob("*.json")} == set(EXPECTED_DECISIONS)


@pytest.mark.parametrize("name", EXPECTED_DECISIONS)
def test_clips_regenerate_byte_for_byte(name):
    """The fixed seed really fixes the clips: regenerating gives the stored WAV bytes."""
    buffer = io.BytesIO()
    sf.write(buffer, make_clips()[name], SR, subtype="PCM_16", format="WAV")
    assert buffer.getvalue() == (CLIPS_DIR / f"{name}.wav").read_bytes()


# --- The comparator itself ----------------------------------------------------------

def test_comparator_accepts_tiny_float_difference():
    assert_matches({"a": 1.0, "b": [1, "x"]}, {"a": 1.0 + 1e-9, "b": [1, "x"]})


def test_comparator_accepts_cross_platform_float32_noise():
    """Real case: an MFCC mean computed on Windows vs Linux."""
    assert_matches({"mfcc_mean_2": 2.6524767875671387}, {"mfcc_mean_2": 2.65246844291687})


@pytest.mark.parametrize("actual", [{"a": 1.001}, {"a": 1.0, "extra": 2}, {"a": "1.0"}, {"a": None}])
def test_comparator_rejects_real_differences(actual):
    with pytest.raises(AssertionError):
        assert_matches(actual, {"a": 1.0})
