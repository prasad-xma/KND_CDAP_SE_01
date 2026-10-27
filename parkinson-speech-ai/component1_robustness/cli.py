"""Command line for the Component 1 quality gate.

Usage (from parkinson-speech-ai/):
    python -m component1_robustness.cli --input recording.m4a --task vowel

Prints a short summary and the path of report.json.
Exit code: 0 = PASS, 1 = FAIL (recording rejected), 2 = usage error.
"""

import argparse
import sys
from pathlib import Path

from component1_robustness.config import load_config, resolve_path
from component1_robustness.pipeline import TASKS, run_gate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m component1_robustness.cli",
                                     description="Component 1 audio quality gate")
    parser.add_argument("--input", required=True, help="recording (.wav, .m4a, .mp3)")
    parser.add_argument("--task", required=True, choices=list(TASKS), help="vowel or ddk")
    parser.add_argument("--config", default=None, help="config YAML (default: configs/component1.yaml)")
    return parser.parse_args(argv)


def print_summary(report: dict, config: dict) -> None:
    """Decision, score, message to the user, where the audio goes, and the report path."""
    print(f"Decision      : {report['decision']} ({report['reason']})")
    print(f"Quality score : {report['quality_score']:.1f} / 100")
    print(f"Message       : {report['user_message']}")
    if report["decision"] == "PASS":
        print(f"Forwarding    : {report['audio_choice']} audio -> {report['next_component']}")
        print(f"Audio         : {report['audio_for_next_stage']}")
    else:
        print("Forwarding    : nothing (recording rejected)")
    print(f"Report        : {resolve_path(config, 'outputs') / report['clip_id'] / 'report.json'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not Path(args.input).is_file():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 2
    config = load_config(args.config)
    report = run_gate(args.input, args.task, config)
    print_summary(report, config)
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
