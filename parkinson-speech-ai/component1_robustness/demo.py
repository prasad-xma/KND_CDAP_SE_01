"""Two-minute demo of Component 1 for the panel.

Run from parkinson-speech-ai/:
    python -m component1_robustness.demo              # full demo (includes the test suite, ~2 min)
    python -m component1_robustness.demo --skip-tests # just the two recordings

1. Runs the gate on one clean and one noisy recording (the golden clips) with
   the real config, and prints the decision, reason and where the audio goes next.
2. Runs the full pytest suite and prints its summary line.
3. Prints the benchmark winner from results/component1_robustness/selected_gate_model.json.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from component1_robustness.benchmark import SELECTED_JSON
from component1_robustness.cli import print_summary
from component1_robustness.config import REPO_ROOT, load_config, resolve_path
from component1_robustness.pipeline import run_gate

GOLDEN_CLIPS = REPO_ROOT / "component1_robustness" / "tests" / "golden" / "clips"
DEMO_CLIPS = [("Clean recording", GOLDEN_CLIPS / "clean_5s.wav"),
              ("Noisy recording (0 dB SNR)", GOLDEN_CLIPS / "noise_0db.wav")]


def show_recording(title: str, path: Path, config: dict) -> None:
    """Run the gate on one clip and print what happened."""
    report = run_gate(path, "vowel", config)
    print(f"\n{title}: {path.name}")
    print_summary(report, config)


def run_tests() -> int:
    """Run the whole Component 1 suite; print only its summary line."""
    print("\nRunning test suite: pytest component1_robustness/tests ...")
    result = subprocess.run([sys.executable, "-m", "pytest", "component1_robustness/tests", "-q",
                             "-p", "no:warnings"], cwd=REPO_ROOT, capture_output=True, text=True)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    print("  " + (lines[-1] if lines else "(no output)"))
    return result.returncode


def show_benchmark_winner(config: dict) -> None:
    path = resolve_path(config, "results") / SELECTED_JSON
    if not path.is_file():
        print("\nBenchmark: not run yet. Run: python -m component1_robustness.labels, "
              "then python -m component1_robustness.benchmark")
        return
    selected = json.loads(path.read_text(encoding="utf-8"))
    print(f"\nBenchmark winner: {selected['selected_gate_model']}")
    print(f"  Why: {selected['reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m component1_robustness.demo")
    parser.add_argument("--skip-tests", action="store_true", help="skip the pytest run")
    args = parser.parse_args(argv)

    config = load_config()
    print(f"Component 1 quality gate demo  (gate: {config['gate_model']}, "
          f"enhancement: {config['enhancement_method']}, config {config['config_version']})")
    for title, path in DEMO_CLIPS:
        show_recording(title, path, config)
    code = 0 if args.skip_tests else run_tests()
    show_benchmark_winner(config)
    return code


if __name__ == "__main__":
    sys.exit(main())
