"""Tests for the Component 1 HTTP API (FastAPI TestClient, synthetic audio only)."""

import io
import os
import subprocess

import imageio_ffmpeg
import jsonschema
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from component1_robustness import api
from component1_robustness.config import load_config
from component1_robustness.pipeline import REPORT_SCHEMA, USER_MESSAGES

from conftest import as_take, gate_config, make_ddk, make_vowel

SR = 16000


@pytest.fixture
def client(tmp_path):
    cfg = gate_config(tmp_path)
    api.app.dependency_overrides[api.get_config] = lambda: cfg
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def _wav_bytes(y: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, y, SR, format="WAV")
    return buffer.getvalue()


def _clean_vowel(seconds: float = 5.0) -> np.ndarray:
    return as_take(make_vowel(duration_s=seconds) + 1e-3 * np.random.default_rng(0).standard_normal(int(seconds * SR)))


def _post(client, data: bytes, filename: str, task: str = "vowel"):
    return client.post("/quality/check", files={"audio": (filename, data, "application/octet-stream")},
                       data={"task": task})


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["component"] == "quality_gate"
    assert body["gate_model"] == load_config()["gate_model"]


def test_clean_wav_passes(client):
    response = _post(client, _wav_bytes(_clean_vowel()), "patient_vowel.wav")
    assert response.status_code == 200
    report = response.json()
    jsonschema.validate(report, REPORT_SCHEMA)
    assert report["decision"] == "PASS"
    assert report["next_component"] == "component2"
    assert os.path.isfile(report["audio_for_next_stage"])


def test_ddk_task_routes_to_component3(client):
    report = _post(client, _wav_bytes(make_ddk()), "patient_ddk.wav", task="ddk").json()
    assert report["decision"] == "PASS" and report["next_component"] == "component3"


def test_1s_wav_fails_too_short_with_200(client):
    response = _post(client, _wav_bytes(_clean_vowel(1.0)), "short.wav")
    assert response.status_code == 200          # a rejected recording is not an HTTP error
    report = response.json()
    assert (report["decision"], report["reason"]) == ("FAIL", "too_short")
    assert report["user_message"] == USER_MESSAGES["too_short"].format(min=1.5)
    assert report["audio_for_next_stage"] is None


@pytest.mark.parametrize("filename", ["notes.txt", "audio.ogg", "noextension"])
def test_unsupported_extension_400(client, filename):
    response = _post(client, b"not audio", filename)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_unknown_task_400(client):
    response = _post(client, _wav_bytes(_clean_vowel()), "v.wav", task="reading")
    assert response.status_code == 400


def test_missing_fields_422(client):
    assert client.post("/quality/check", data={"task": "vowel"}).status_code == 422


def test_corrupt_wav_422(client):
    response = _post(client, b"RIFF this is not really a wav file", "broken.wav")
    assert response.status_code == 422
    assert "Could not read" in response.json()["detail"]


def test_m4a_upload(client, tmp_path):
    # 4.5 s, not 5 s: AAC encoding adds ~0.06 s of padding, and the gate's maximum is 5.0 s.
    wav = tmp_path / "phone.wav"
    sf.write(wav, _clean_vowel(4.5), SR)
    m4a = tmp_path / "phone.m4a"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav), str(m4a)],
                   check=True)
    report = _post(client, m4a.read_bytes(), "phone.m4a").json()
    jsonschema.validate(report, REPORT_SCHEMA)
    assert report["decision"] == "PASS"


def test_filename_is_sanitised(client):
    report = _post(client, _wav_bytes(_clean_vowel()), "../../my recording (1).wav").json()
    assert report["clip_id"].startswith("my_recording_1_")


def test_upload_temp_files_removed(client, tmp_path, monkeypatch):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(scratch))
    _post(client, _wav_bytes(_clean_vowel()), "v.wav")
    assert list(scratch.iterdir()) == []


@pytest.mark.parametrize("filename,expected", [("a.wav", "a"), ("../x/y z.m4a", "y_z"), ("", "upload"),
                                               ("***.wav", "upload")])
def test_safe_stem(filename, expected):
    assert api._safe_stem(filename) == expected
