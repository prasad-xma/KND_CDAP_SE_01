"""Generate the golden regression set: 7 seeded synthetic clips + their expected reports.

Run from parkinson-speech-ai/ ONLY when a change to the outputs is intended:
    python component1_robustness/tests/golden/generate.py

Then review the diff of expected/*.json in git before committing: every changed
number is a behaviour change. test_golden_set.py re-runs the pipeline on the
stored clips and compares against these files.
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

GOLDEN_DIR = Path(__file__).resolve().parent
TESTS_DIR = GOLDEN_DIR.parent
REPO_ROOT = TESTS_DIR.parents[1]
for p in (str(REPO_ROOT), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from conftest import make_vowel  # noqa: E402
from component1_robustness.config import load_config  # noqa: E402
from component1_robustness.pipeline import run_gate  # noqa: E402

CLIPS_DIR = GOLDEN_DIR / "clips"
EXPECTED_DIR = GOLDEN_DIR / "expected"
CONFIG_PATH = GOLDEN_DIR / "config_golden.yaml"
SEED = 20261025
SR = 16000
TASK = "vowel"


def _voice(duration_s: float, rng: np.random.Generator) -> np.ndarray:
    """150 Hz harmonic vowel with a 4 Hz loudness wobble and a faint hiss (about -50 dB)."""
    t = np.arange(int(duration_s * SR)) / SR
    y = make_vowel(duration_s=duration_s) * (1 + 0.05 * np.sin(2 * np.pi * 4 * t))
    return y + 1e-3 * rng.standard_normal(len(y))


def _add_noise(y: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    noise = rng.standard_normal(len(y))
    noisy = y + noise * np.sqrt(np.mean(y ** 2) / np.mean(noise ** 2)) / 10 ** (snr_db / 20)
    return 0.9 * noisy / np.max(np.abs(noisy))   # keep below full scale: these test noise, not clipping


def make_clips() -> dict[str, np.ndarray]:
    """The 7 golden clips, fully determined by SEED."""
    rng = np.random.default_rng(SEED)
    clean = _voice(5.0, rng)
    return {
        "clean_5s": clean,
        "noise_20db": _add_noise(clean, 20, rng),
        "noise_5db": _add_noise(clean, 5, rng),
        "noise_0db": _add_noise(clean, 0, rng),
        "clipped": np.clip(4.0 * clean, -1.0, 1.0),
        "short_2p9s": _voice(2.9, rng),
        "long_15p1s": _voice(15.1, rng),
    }


def golden_config(outputs_dir: str | Path) -> dict:
    cfg = load_config(CONFIG_PATH)
    cfg["paths"] = dict(cfg["paths"], outputs=str(outputs_dir))
    return cfg


def normalise(report: dict, outputs_dir: str | Path) -> dict:
    """Make a report machine-independent: forwarded path relative to the outputs folder."""
    report = dict(report)
    if report["audio_for_next_stage"]:
        report["audio_for_next_stage"] = Path(report["audio_for_next_stage"]).relative_to(outputs_dir).as_posix()
    return report


def main() -> None:
    CLIPS_DIR.mkdir(exist_ok=True)
    EXPECTED_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as outputs:
        cfg = golden_config(outputs)
        for name, y in make_clips().items():
            wav = CLIPS_DIR / f"{name}.wav"
            sf.write(wav, y, SR, subtype="PCM_16")
            report = normalise(run_gate(wav, TASK, cfg), outputs)
            text = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
            (EXPECTED_DIR / f"{name}.json").write_text(text + "\n", encoding="utf-8", newline="\n")
            print(f"{name:12s} {report['decision']:4s} {report['reason']:10s} -> {report['audio_choice']}")


if __name__ == "__main__":
    main()
