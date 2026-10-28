"""Tests for demo.py (the pytest step is stubbed so the suite does not run itself)."""

import json

import pytest

from component1_robustness import demo
from conftest import gate_config


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    c = gate_config(tmp_path)
    c["paths"]["results"] = str(tmp_path / "results")
    monkeypatch.setattr(demo, "load_config", lambda: c)
    return c


def test_demo_clips_exist():
    assert all(path.is_file() for _, path in demo.DEMO_CLIPS)


def test_demo_prints_both_decisions(cfg, capsys):
    assert demo.main(["--skip-tests"]) == 0
    out = capsys.readouterr().out
    assert "Decision      : PASS" in out and "component2" in out
    assert "Decision      : FAIL (low_snr)" in out and "Forwarding    : nothing" in out
    assert "Benchmark: not run yet" in out


def test_demo_prints_benchmark_winner(cfg, tmp_path, capsys):
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / demo.SELECTED_JSON).write_text(
        json.dumps({"selected_gate_model": "comp1-B-rf", "reason": "lowest FAR"}), encoding="utf-8")
    demo.main(["--skip-tests"])
    assert "Benchmark winner: comp1-B-rf" in capsys.readouterr().out


def test_demo_runs_test_step_and_returns_its_code(cfg, monkeypatch, capsys):
    monkeypatch.setattr(demo, "run_tests", lambda: 1)
    assert demo.main([]) == 1
