"""Old entry point for validating the quality gate, kept so this still works:

    python -m component1_robustness.validate_quality_gate

The evaluation now lives in benchmark.py, which uses PER-CLIP labels
(labels.py) and participant-grouped cross-validation instead of labelling
every clip in a condition the same way. This wrapper runs that benchmark for
comp1-A only and prints the metrics. It writes no files and does not change
the config or the selected model; run benchmark.py for the full comparison.
"""

from component1_robustness.benchmark import run_benchmark
from component1_robustness.config import load_config


def main(config: dict | None = None) -> dict | None:
    """Benchmark comp1-A only; print-only (no outputs, no selection)."""
    return run_benchmark(config or load_config(), model_names=["comp1-A"],
                         select=False, save_outputs=False, write_back=False)


if __name__ == "__main__":
    main()
