"""End-to-end tests for pipeline.run_gate, on synthetic recordings only."""

import hashlib
import json
import math
import subprocess

import imageio_ffmpeg
import jsonschema
import numpy as np
import pytest
import soundfile as sf

from component1_robustness import pipeline
from component1_robustness.config import load_config
from component1_robustness.pipeline import REPORT_SCHEMA, json_safe, make_clip_id, run_gate

from conftest import make_ddk, make_vowel

SR = 16000
OUTPUT_FILES = {"raw.wav", "enhanced.wav", "waveform.png", "spectrogram.png", "report.json"}


def _config(tmp_path, **overrides) -> dict:
    cfg = load_config()
    cfg["paths"] = dict(cfg["paths"], outputs=str(tmp_path / "outputs"))
    cfg.update(overrides)
    return cfg


def _natural_vowel(duration_s: float = 5.0, seed: int = 3) -> np.ndarray:
    """Vowel with a slight loudness wobble and a faint noise floor, like a quiet-room recording."""
    t = np.arange(int(duration_s * SR)) / SR
    hiss = 1e-3 * np.random.default_rng(seed).standard_normal(len(t))
    return make_vowel(duration_s=duration_s) * (1 + 0.05 * np.sin(2 * np.pi * 4 * t)) + hiss


def _wav(tmp_path, name: str, y: np.ndarray) -> str:
    path = tmp_path / name
    sf.write(path, y, SR)
    return str(path)


def _noisy_0db(y: np.ndarray) -> np.ndarray:
    noise = np.random.default_rng(11).standard_normal(len(y))
    noisy = y + noise * np.sqrt(np.mean(y ** 2) / np.mean(noise ** 2))
    return 0.9 * noisy / np.max(np.abs(noisy))


@pytest.fixture(scope="module")
def vowel_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("vowel")
    cfg = _config(tmp)
    report = run_gate(_wav(tmp, "patient_vowel.wav", _natural_vowel()), "vowel", cfg)
    return report, cfg, tmp


# --- Report schema and files ----------------------------------------------------

def test_pass_report_matches_schema(vowel_run):
    report, _, _ = vowel_run
    jsonschema.validate(report, REPORT_SCHEMA)


def test_report_json_on_disk_equals_returned_report(vowel_run):
    report, cfg, tmp = vowel_run
    on_disk = json.loads((tmp / "outputs" / report["clip_id"] / "report.json").read_text(encoding="utf-8"))
    assert on_disk == report
    jsonschema.validate(on_disk, REPORT_SCHEMA)


def test_all_output_files_written(vowel_run):
    report, _, tmp = vowel_run
    folder = tmp / "outputs" / report["clip_id"]
    assert {p.name for p in folder.iterdir()} == OUTPUT_FILES
    assert all((folder / name).stat().st_size > 0 for name in OUTPUT_FILES)


def test_report_has_no_timestamps(vowel_run):
    report, _, _ = vowel_run
    text = json.dumps(report).lower()
    assert not any(word in text for word in ("time", "date", "created"))


def test_clip_id_and_hash(vowel_run):
    report, _, tmp = vowel_run
    expected = hashlib.sha256((tmp / "patient_vowel.wav").read_bytes()).hexdigest()
    assert report["input_sha256"] == expected
    assert report["clip_id"] == f"patient_vowel_{expected[:8]}" == make_clip_id("x/patient_vowel.wav", expected)


def test_config_version_recorded(vowel_run):
    report, cfg, _ = vowel_run
    assert report["config_version"] == cfg["config_version"]


# --- Decisions and routing ------------------------------------------------------

def test_clean_vowel_passes_to_component2(vowel_run):
    report, _, _ = vowel_run
    assert report["decision"] == "PASS" and report["reason"] == "ok"
    assert report["next_component"] == "component2"
    assert report["audio_choice"] in {"enhanced", "raw"}
    assert report["audio_for_next_stage"].endswith(f"{report['audio_choice']}.wav")


def test_clean_ddk_passes_to_component3(tmp_path):
    report = run_gate(_wav(tmp_path, "patient_ddk.wav", make_ddk()), "ddk", _config(tmp_path))
    jsonschema.validate(report, REPORT_SCHEMA)
    assert report["decision"] == "PASS"
    assert report["next_component"] == "component3"


def test_ddk_preservation_uses_component3_features(tmp_path):
    """The audio goes to Component 3, so its DDK features are the ones checked."""
    from component3_ddk.features import FEATURE_NAMES as DDK_FEATURE_NAMES
    cfg = _config(tmp_path)
    report = run_gate(_wav(tmp_path, "d.wav", make_ddk()), "ddk", cfg)
    assert list(report["features_before"]) == DDK_FEATURE_NAMES
    assert set(report["feature_preserved"]["per_feature"]) == set(cfg["ddk_feature_tolerances"])


def test_0db_noisy_clip_fails_with_reason_and_message(tmp_path):
    cfg = _config(tmp_path)
    report = run_gate(_wav(tmp_path, "noisy.wav", _noisy_0db(_natural_vowel())), "vowel", cfg)
    jsonschema.validate(report, REPORT_SCHEMA)
    assert report["decision"] == "FAIL"
    assert report["reason"] == "low_snr"
    assert report["user_message"] == pipeline.USER_MESSAGES["low_snr"]
    assert report["audio_for_next_stage"] is None
    assert report["audio_choice"] is None and report["next_component"] is None


@pytest.mark.parametrize("seconds,reason", [(2.9, "too_short"), (15.1, "too_long")])
def test_duration_fail_stops_before_enhancement(tmp_path, monkeypatch, seconds, reason):
    def must_not_run(*args, **kwargs):
        raise AssertionError("enhance() must not run for a clip of the wrong length")
    monkeypatch.setattr(pipeline, "enhance", must_not_run)

    report = run_gate(_wav(tmp_path, "clip.wav", _natural_vowel(seconds)), "vowel", _config(tmp_path))
    jsonschema.validate(report, REPORT_SCHEMA)
    assert (report["decision"], report["reason"], report["quality_score"]) == ("FAIL", reason, 0.0)
    assert report["duration_s"] == pytest.approx(seconds, abs=1e-3)
    assert report["quality_before"] is None and report["features_before"] is None
    assert "seconds" in report["user_message"]
    folder = tmp_path / "outputs" / report["clip_id"]
    assert {p.name for p in folder.iterdir()} == {"raw.wav", "report.json"}


def test_preserved_forwards_enhanced(tmp_path):
    """Enhancement 'none' changes nothing, so features are preserved and enhanced.wav is sent."""
    report = run_gate(_wav(tmp_path, "v.wav", _natural_vowel()), "vowel",
                      _config(tmp_path, enhancement_method="none"))
    assert report["feature_preserved"]["preserved"] is True
    assert report["audio_choice"] == "enhanced"
    assert report["audio_for_next_stage"].endswith("enhanced.wav")


def test_not_preserved_forwards_raw(tmp_path):
    """A tolerance no real change can meet: any enhancement 'alters biomarkers', so raw.wav is sent."""
    tight = {k: 1e-12 for k in load_config()["feature_tolerances"]}
    report = run_gate(_wav(tmp_path, "v.wav", _natural_vowel()), "vowel",
                      _config(tmp_path, enhancement_method="wiener", feature_tolerances=tight))
    assert report["decision"] == "PASS"
    assert report["feature_preserved"]["preserved"] is False
    assert report["audio_choice"] == "raw"
    assert report["audio_for_next_stage"].endswith("raw.wav")


def test_forwarded_audio_is_standardised(vowel_run):
    report, _, tmp = vowel_run
    info = sf.info(report["audio_for_next_stage"])
    # Forwarded audio keeps the input's own sample rate (no resampling).
    assert info.samplerate == sf.info(tmp / "patient_vowel.wav").samplerate and info.channels == 1


# --- Determinism ------------------------------------------------------------------

def test_same_input_twice_identical_report_bytes(tmp_path):
    cfg = _config(tmp_path)
    path = _wav(tmp_path, "v.wav", _natural_vowel())
    first = run_gate(path, "vowel", cfg)
    folder = tmp_path / "outputs" / first["clip_id"]
    before = {name: (folder / name).read_bytes() for name in OUTPUT_FILES}
    run_gate(path, "vowel", cfg)
    after = {name: (folder / name).read_bytes() for name in OUTPUT_FILES}
    assert after["report.json"] == before["report.json"]
    assert after == before   # wavs and PNGs too


# --- Input handling -----------------------------------------------------------------

def test_m4a_input_is_converted_and_temp_wav_removed(tmp_path, monkeypatch):
    wav = _wav(tmp_path, "phone.wav", _natural_vowel())
    m4a = tmp_path / "phone.m4a"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", wav, str(m4a)],
                   check=True)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    report = run_gate(str(m4a), "vowel", _config(tmp_path))
    jsonschema.validate(report, REPORT_SCHEMA)
    assert report["clip_id"].startswith("phone_")
    assert list((tmp_path / "tmp").iterdir()) == []   # converted WAV cleaned up


def test_keeps_native_sample_rate(tmp_path):
    path = tmp_path / "v8k.wav"
    sf.write(path, make_vowel(duration_s=4.0, sr=8000), 8000)
    report = run_gate(str(path), "vowel", _config(tmp_path))
    assert sf.info(tmp_path / "outputs" / report["clip_id"] / "raw.wav").samplerate == 8000
    assert report["duration_s"] == pytest.approx(4.0, abs=1e-3)


def test_unknown_task_raises(tmp_path):
    with pytest.raises(ValueError):
        run_gate(_wav(tmp_path, "v.wav", _natural_vowel()), "reading", _config(tmp_path))


@pytest.mark.parametrize("value,expected", [
    (np.float32(1.5), 1.5), (np.int64(3), 3), (np.bool_(True), True), (math.inf, None),
    (-math.inf, None), (math.nan, None), ({"a": [np.float64(2.0), -math.inf]}, {"a": [2.0, None]}),
])
def test_json_safe(value, expected):
    assert json_safe(value) == expected


def test_every_gate_reason_has_a_user_message():
    for reason in ("ok", "too_short", "too_long", "clipped", "no_voice", "low_snr", "low_quality"):
        assert pipeline.user_message(reason, load_config())


def _wav_chunk_ids(data: bytes) -> list[bytes]:
    pos, ids = 12, []
    while pos < len(data):
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        ids.append(data[pos:pos + 4])
        pos += 8 + size + (size & 1)
    return ids


@pytest.mark.parametrize("name", ["raw.wav", "enhanced.wav"])
def test_output_wavs_have_no_timestamp_chunks(vowel_run, name):
    """libsndfile's PEAK chunk (float WAVs) holds a timestamp; outputs must not contain one."""
    report, _, tmp = vowel_run
    ids = _wav_chunk_ids((tmp / "outputs" / report["clip_id"] / name).read_bytes())
    assert ids == [b"fmt ", b"data"]
