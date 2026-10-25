"""check_quality() must keep its old interface (screening/predict_screening.py uses it)."""

import dataclasses

import numpy as np
import pytest
import soundfile as sf

from component1_robustness import quality_gate
from component1_robustness.quality_gate import QualityGateResult, check_quality

SR = 16000
EXPECTED_FIELDS = ["passed", "estimated_snr_db", "method", "level_dbfs", "message"]


@pytest.fixture
def clean_wav(tmp_path, tone):
    path = tmp_path / "clean_tone.wav"
    sf.write(path, tone, SR)
    return str(path)


@pytest.fixture
def noisy_wav(tmp_path, tone):
    noise = np.random.default_rng(0).standard_normal(len(tone))
    noisy = tone + noise * np.sqrt(np.mean(tone ** 2)) / np.sqrt(np.mean(noise ** 2))  # 0 dB SNR
    path = tmp_path / "noisy_tone.wav"
    sf.write(path, noisy / np.max(np.abs(noisy)) * 0.9, SR)
    return str(path)


def test_result_dataclass_fields_unchanged():
    assert [f.name for f in dataclasses.fields(QualityGateResult)] == EXPECTED_FIELDS


def test_check_quality_returns_result(clean_wav):
    result = check_quality(clean_wav)
    assert isinstance(result, QualityGateResult)
    assert isinstance(result.passed, bool)
    assert isinstance(result.message, str) and result.message
    assert result.method in {"silence_snr", "hnr"}


def test_check_quality_clean_passes_noisy_fails(clean_wav, noisy_wav):
    assert check_quality(clean_wav).passed is True
    assert check_quality(noisy_wav).passed is False


def test_level_floor_is_opt_in(clean_wav):
    assert check_quality(clean_wav).passed is True
    assert check_quality(clean_wav, min_level_dbfs=0.0).passed is False  # nothing is that loud


def test_asdict_still_works(clean_wav):
    """screening/predict_screening.py calls dataclasses.asdict() on the result."""
    assert list(dataclasses.asdict(check_quality(clean_wav))) == EXPECTED_FIELDS


def test_old_names_still_importable():
    assert quality_gate.RELIABLE_DB == 10.0
    assert callable(quality_gate.estimate_quality_db)
