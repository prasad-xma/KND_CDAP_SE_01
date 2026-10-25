"""Tests for cli.py."""

import numpy as np
import pytest
import soundfile as sf
import yaml

from component1_robustness import cli
from component1_robustness.config import load_config

from conftest import make_ddk, make_vowel

SR = 16000


@pytest.fixture
def config_file(tmp_path):
    cfg = load_config()
    cfg["paths"] = dict(cfg["paths"], outputs=str(tmp_path / "outputs"))
    path = tmp_path / "c1.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(path)


def _wav(tmp_path, name, y):
    path = tmp_path / name
    sf.write(path, y, SR)
    return str(path)


def test_pass_exit_code_0(tmp_path, config_file, capsys):
    y = make_vowel() + 1e-3 * np.random.default_rng(0).standard_normal(SR * 5)
    code = cli.main(["--input", _wav(tmp_path, "v.wav", y), "--task", "vowel", "--config", config_file])
    out = capsys.readouterr().out
    assert code == 0
    assert "Decision      : PASS" in out and "component2" in out and "report.json" in out


def test_ddk_task(tmp_path, config_file, capsys):
    assert cli.main(["--input", _wav(tmp_path, "d.wav", make_ddk()), "--task", "ddk", "--config", config_file]) == 0
    assert "component3" in capsys.readouterr().out


def test_fail_exit_code_1(tmp_path, config_file, capsys):
    code = cli.main(["--input", _wav(tmp_path, "s.wav", make_vowel(duration_s=2.0)), "--task", "vowel",
                     "--config", config_file])
    assert code == 1
    assert "too_short" in capsys.readouterr().out


def test_missing_file_exit_code_2(tmp_path, capsys):
    assert cli.main(["--input", str(tmp_path / "nope.wav"), "--task", "vowel"]) == 2
    assert "not found" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--task", "vowel"], ["--input", "x.wav"], ["--input", "x.wav", "--task", "song"]])
def test_bad_arguments_exit_2(argv):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
