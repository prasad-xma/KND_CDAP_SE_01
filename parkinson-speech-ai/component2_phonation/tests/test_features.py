"""Tests for component2_phonation.features.extract_phonation_features."""

import soundfile as sf

from component2_phonation.features import FEATURE_NAMES, extract_phonation_features

from conftest import TEST_F0_HZ, TEST_SR, make_silence, make_vowel


def _write_wav(tmp_path, y, name="clip.wav", sr=TEST_SR):
    path = tmp_path / name
    sf.write(path, y, sr)
    return str(path)


def test_silence_returns_none(tmp_path):
    path = _write_wav(tmp_path, make_silence())
    assert extract_phonation_features(path) is None


def test_vowel_returns_all_feature_names(tmp_path):
    path = _write_wav(tmp_path, make_vowel())
    features = extract_phonation_features(path)
    assert set(features.keys()) == set(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in features.values())


def test_mean_f0_matches_known_tone(tmp_path):
    path = _write_wav(tmp_path, make_vowel())
    features = extract_phonation_features(path)
    assert abs(features["mean_f0"] - TEST_F0_HZ) < 5.0


def test_clean_tone_has_low_jitter_and_shimmer(tmp_path):
    """A perfectly periodic synthetic tone should look nothing like a pathological voice."""
    path = _write_wav(tmp_path, make_vowel())
    features = extract_phonation_features(path)
    assert features["jitter"] < 0.01
    assert features["shimmer"] < 0.01
    assert features["hnr"] > 15.0
