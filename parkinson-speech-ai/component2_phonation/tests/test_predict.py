"""Tests for component2_phonation.predict (real trained models, synthetic audio)."""

import os

import pytest
import soundfile as sf

from component2_phonation.predict import REPO_ROOT, model_path_for, predict

from conftest import TEST_SR, make_silence, make_vowel

VOWEL_COMBINED_TUNED_PATH = os.path.join(
    REPO_ROOT, "models", "component2_phonation_vowel_combined_tuned.joblib"
)


def _write_wav(tmp_path, y, name="clip.wav", sr=TEST_SR):
    path = tmp_path / name
    sf.write(path, y, sr)
    return str(path)


@pytest.fixture(autouse=True, scope="module")
def _models_exist():
    assert os.path.isfile(VOWEL_COMBINED_TUNED_PATH), "production model missing - run training first"
    assert os.path.isfile(model_path_for("readtext"))


def test_predict_on_vowel_tone_returns_valid_result(tmp_path):
    path = _write_wav(tmp_path, make_vowel())
    result = predict(path, model_path=VOWEL_COMBINED_TUNED_PATH)

    assert result["prediction"] in ("PD", "HC")
    assert result["probability_hc"] + result["probability_pd"] == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= result["probability_pd"] <= 1.0
    assert set(result["features"].keys())


def test_predict_on_silence_raises_value_error(tmp_path):
    path = _write_wav(tmp_path, make_silence())
    with pytest.raises(ValueError, match="No voiced frames detected"):
        predict(path, model_path=VOWEL_COMBINED_TUNED_PATH)


def test_model_path_for_readtext_matches_the_file_api_uses():
    assert model_path_for("readtext") == os.path.join(
        REPO_ROOT, "models", "component2_phonation_readtext_rf.joblib"
    )
