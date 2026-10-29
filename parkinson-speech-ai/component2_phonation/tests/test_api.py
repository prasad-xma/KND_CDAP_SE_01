"""Tests for the Component 2 HTTP API (FastAPI TestClient, synthetic audio only)."""

import io
import subprocess

import imageio_ffmpeg
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from component2_phonation import api

from conftest import TEST_SR, make_silence, make_vowel


@pytest.fixture
def client():
    return TestClient(api.app)


def _wav_bytes(y: np.ndarray, sr: int = TEST_SR) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, y, sr, format="WAV")
    return buffer.getvalue()


def _post_single(client, data: bytes, filename: str = "v.wav", extract_vowel_segment: bool = True):
    return client.post(
        "/phonation/screen",
        files={"audio": (filename, data, "application/octet-stream")},
        data={"extract_vowel_segment": str(extract_vowel_segment)},
    )


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["component"] == "phonation"
    assert body["model_found"] is True


def test_vowel_segment_mode_returns_vowel_combined_tuned(client):
    response = _post_single(client, _wav_bytes(make_vowel()), extract_vowel_segment=True)
    assert response.status_code == 200
    body = response.json()
    assert body["model_used"] == "vowel_combined_tuned"
    assert body["extraction_used"] is True
    assert body["prediction"] in ("PD", "HC")
    assert body["probability_pd"] + body["probability_hc"] == pytest.approx(1.0, abs=1e-6)
    assert "segment_start_seconds" in body


def test_whole_recording_mode_returns_readtext_model(client):
    response = _post_single(client, _wav_bytes(make_vowel()), extract_vowel_segment=False)
    assert response.status_code == 200
    body = response.json()
    assert body["model_used"] == "readtext"
    assert body["extraction_used"] is False
    assert "segment_start_seconds" not in body


def test_unsupported_extension_400(client):
    response = _post_single(client, b"not audio", filename="notes.txt")
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_silence_with_extraction_422(client):
    response = _post_single(client, _wav_bytes(make_silence()), extract_vowel_segment=True)
    assert response.status_code == 422
    assert "No sustained vowel-like segment" in response.json()["detail"]


def test_silence_without_extraction_422(client):
    response = _post_single(client, _wav_bytes(make_silence()), extract_vowel_segment=False)
    assert response.status_code == 422
    assert "No voiced frames detected" in response.json()["detail"]


def test_m4a_upload(client, tmp_path):
    wav_path = tmp_path / "phone.wav"
    sf.write(wav_path, make_vowel(), TEST_SR)
    m4a_path = tmp_path / "phone.m4a"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav_path), str(m4a_path)],
        check=True,
    )
    response = _post_single(client, m4a_path.read_bytes(), filename="phone.m4a", extract_vowel_segment=True)
    assert response.status_code == 200
    assert response.json()["model_used"] == "vowel_combined_tuned"


def test_upload_temp_files_removed(client, tmp_path, monkeypatch):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(scratch))
    _post_single(client, _wav_bytes(make_vowel()), extract_vowel_segment=True)
    assert list(scratch.iterdir()) == []


def test_vowel_multi_averages_the_individual_probabilities(client):
    files = [
        ("audio_files", (f"v{i}.wav", _wav_bytes(make_vowel()), "application/octet-stream"))
        for i in range(3)
    ]
    response = client.post("/phonation/screen_vowel_multi", files=files)
    assert response.status_code == 200
    body = response.json()
    assert len(body["recordings"]) == 3
    expected = sum(r["probability_pd"] for r in body["recordings"]) / 3
    assert body["probability_pd"] == pytest.approx(expected, abs=1e-9)
    assert body["prediction"] == ("PD" if body["probability_pd"] >= 0.5 else "HC")


def test_dual_fuses_vowel_and_phrase_results(client):
    response = client.post(
        "/phonation/screen_dual",
        files={
            "vowel_audio": ("v.wav", _wav_bytes(make_vowel()), "application/octet-stream"),
            "phrase_audio": ("p.wav", _wav_bytes(make_vowel()), "application/octet-stream"),
        },
    )
    assert response.status_code == 200
    body = response.json()
    expected = (body["vowel_task"]["probability_pd"] + body["phrase_task"]["probability_pd"]) / 2
    assert body["probability_pd"] == pytest.approx(expected, abs=1e-9)
    assert body["vowel_task"]["model_used"] == "vowel_combined_tuned"
    assert body["phrase_task"]["model_used"] == "readtext"
