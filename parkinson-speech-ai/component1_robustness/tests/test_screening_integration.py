"""screening/predict_screening.py now uses run_gate; its output structure must not change."""

import dataclasses

import pytest

from screening import predict_screening
from screening.predict_screening import ScreeningResult, print_report, run_screening

from conftest import clean_take, gate_config, make_ddk, make_vowel, write_wav

OLD_RESULT_FIELDS = ["stage_reached", "quality_gate_vowel", "quality_gate_ddk", "score_a_phonation",
                     "score_b_speech_motor", "fused_score", "classification", "message"]
OLD_GATE_KEYS = ["passed", "estimated_snr_db", "method", "level_dbfs", "message"]


@pytest.fixture
def cfg(tmp_path):
    return gate_config(tmp_path)


@pytest.fixture
def recordings(tmp_path):
    return write_wav(tmp_path, "vowel.wav", clean_take()), write_wav(tmp_path, "ddk.wav", make_ddk())


def test_result_fields_unchanged():
    assert [f.name for f in dataclasses.fields(ScreeningResult)] == OLD_RESULT_FIELDS


def test_components_receive_forwarded_audio(recordings, cfg, monkeypatch):
    seen = {}
    real_c2, real_c3 = predict_screening.extract_phonation_features, predict_screening.extract_ddk_features
    monkeypatch.setattr(predict_screening, "extract_phonation_features",
                        lambda p: seen.setdefault("c2", p) and real_c2(p))
    monkeypatch.setattr(predict_screening, "extract_ddk_features",
                        lambda p: seen.setdefault("c3", p) and real_c3(p))

    result = run_screening(*recordings, config=cfg)
    outputs = cfg["paths"]["outputs"]
    assert seen["c2"].startswith(outputs) and seen["c2"].endswith((".wav"))
    assert seen["c3"].startswith(outputs) and seen["c3"].endswith((".wav"))
    assert seen["c2"] != recordings[0] and seen["c3"] != recordings[1]
    assert result.stage_reached in {"complete", "feature_extraction_failed"}


def test_gate_dicts_keep_old_keys(recordings, cfg):
    result = run_screening(*recordings, config=cfg)
    assert list(result.quality_gate_vowel) == OLD_GATE_KEYS
    assert list(result.quality_gate_ddk) == OLD_GATE_KEYS
    assert result.quality_gate_vowel["passed"] is True


def test_rejected_recording_stops_at_quality_gate(recordings, cfg, tmp_path, capsys):
    short = write_wav(tmp_path, "short.wav", make_vowel(duration_s=1.0))
    result = run_screening(short, recordings[1], config=cfg)
    assert result.stage_reached == "quality_gate"
    assert "sustained vowel" in result.message
    assert result.quality_gate_vowel["passed"] is False
    assert result.score_a_phonation is None
    print_report(short, recordings[1], result)
    assert "Stopped at: quality_gate" in capsys.readouterr().out


def test_to_json_still_works(recordings, cfg):
    assert '"stage_reached"' in run_screening(*recordings, config=cfg).to_json()
