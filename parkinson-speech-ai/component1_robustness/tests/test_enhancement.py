"""Tests for enhancement.py, using synthetic signals only."""

import noisereduce as nr
import numpy as np
import pytest
import soundfile as sf

from component1_robustness.config import load_config
from component1_robustness.enhancement import METHODS, enhance, enhance_audio

SR = 16000
SEED = load_config()["seed"]


def _true_snr_db(clean: np.ndarray, x: np.ndarray) -> float:
    """SNR of x against the known clean reference: clean energy / residual energy."""
    return float(10 * np.log10(np.sum(clean ** 2) / np.sum((x - clean) ** 2)))


@pytest.fixture
def noisy_vowel_5db(vowel) -> np.ndarray:
    noise = np.random.default_rng(SEED).standard_normal(len(vowel))
    noise *= np.sqrt(np.mean(vowel ** 2)) / np.sqrt(np.mean(noise ** 2)) / 10 ** (5 / 20)
    return vowel + noise


def test_config_default_method_is_supported():
    assert load_config()["enhancement_method"] in METHODS


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("n", [SR * 5, SR * 3 + 777])   # include an odd length
def test_output_length_equals_input(method, n, noisy_vowel_5db):
    y = noisy_vowel_5db[:n]
    assert len(enhance(y, SR, method, SEED)) == n


@pytest.mark.parametrize("method", METHODS)
def test_same_input_twice_identical_output(method, noisy_vowel_5db):
    a = enhance(noisy_vowel_5db, SR, method, SEED)
    b = enhance(noisy_vowel_5db, SR, method, SEED)
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("method", METHODS)
def test_output_is_finite_on_silence(method):
    assert np.all(np.isfinite(enhance(np.zeros(SR * 3), SR, method, SEED)))


def test_none_returns_equal_copy(vowel):
    out = enhance(vowel, SR, "none", SEED)
    np.testing.assert_array_equal(out, vowel)
    assert out is not vowel


def test_unknown_method_raises(vowel):
    with pytest.raises(ValueError):
        enhance(vowel, SR, "magic", SEED)


def test_wiener_improves_snr_at_5db(vowel, noisy_vowel_5db):
    before = _true_snr_db(vowel, noisy_vowel_5db)
    after = _true_snr_db(vowel, enhance(noisy_vowel_5db, SR, "wiener", SEED))
    assert after > before


# --- noisereduce: SNR improvement and its known limitation --------------------

def _si_sdr_db(clean: np.ndarray, x: np.ndarray) -> float:
    """Scale-invariant SNR: project x onto clean first, so an overall level change is not 'noise'.

    Spectral gating also lowers the overall level (here to ~34% of the vowel),
    which plain SNR wrongly counts as error; SI-SDR measures only what is
    left that is not the clean signal.
    """
    scale = np.dot(x, clean) / np.dot(clean, clean)
    target = scale * clean
    return float(10 * np.log10(np.sum(target ** 2) / np.sum((x - target) ** 2)))


@pytest.fixture
def noise_only_1s(noisy_vowel_5db, vowel) -> np.ndarray:
    """1 s of noise only (like a lead-in before the vowel), same level, different seed."""
    noise_rms = np.sqrt(np.mean((noisy_vowel_5db - vowel) ** 2))
    return np.random.default_rng(SEED + 1).standard_normal(SR) * noise_rms


def test_si_sdr_known_answers(vowel, noisy_vowel_5db):
    assert _si_sdr_db(vowel, noisy_vowel_5db) == pytest.approx(5.0, abs=0.1)
    assert _si_sdr_db(vowel, 0.3 * noisy_vowel_5db) == pytest.approx(5.0, abs=0.1)  # level-invariant


@pytest.mark.parametrize("method", ["wiener", "noisereduce_stationary"])
def test_snr_improves_with_noise_ref(method, vowel, noisy_vowel_5db, noise_only_1s):
    before = _si_sdr_db(vowel, noisy_vowel_5db)
    after = _si_sdr_db(vowel, enhance(noisy_vowel_5db, SR, method, SEED, noise_ref=noise_only_1s))
    assert after > before


def test_stationary_with_noise_ref_beats_without(vowel, noisy_vowel_5db, noise_only_1s):
    without = _si_sdr_db(vowel, enhance(noisy_vowel_5db, SR, "noisereduce_stationary", SEED))
    with_ref = _si_sdr_db(vowel, enhance(noisy_vowel_5db, SR, "noisereduce_stationary", SEED,
                                         noise_ref=noise_only_1s))
    assert with_ref > without + 10.0


@pytest.mark.parametrize("noise_ref_given", [False, True])
def test_nonstationary_removes_steady_vowel_known_limitation(vowel, noisy_vowel_5db, noise_only_1s,
                                                             noise_ref_given):
    """Records the limitation, so a fix (or a library change) makes this test fail on purpose.

    Non-stationary gating treats anything steady as noise, so a sustained
    vowel is mostly removed and SNR gets worse, with or without a noise sample.
    """
    ref = noise_only_1s if noise_ref_given else None
    out = enhance(noisy_vowel_5db, SR, "noisereduce_nonstationary", SEED, noise_ref=ref)
    level_kept = np.sqrt(np.mean(out ** 2) / np.mean(vowel ** 2))
    assert level_kept < 0.2
    assert _si_sdr_db(vowel, out) < _si_sdr_db(vowel, noisy_vowel_5db)


def test_stationary_without_noise_ref_known_limitation(vowel, noisy_vowel_5db):
    """Without a noise sample, stationary gating also takes the vowel for noise."""
    out = enhance(noisy_vowel_5db, SR, "noisereduce_stationary", SEED)
    assert _si_sdr_db(vowel, out) < _si_sdr_db(vowel, noisy_vowel_5db)


@pytest.mark.parametrize("method", ["wiener", "none", "noisereduce_nonstationary"])
def test_noise_ref_ignored_by_other_methods(method, noisy_vowel_5db, noise_only_1s):
    a = enhance(noisy_vowel_5db, SR, method, SEED)
    b = enhance(noisy_vowel_5db, SR, method, SEED, noise_ref=noise_only_1s)
    np.testing.assert_array_equal(a, b)


# --- Backward-compatible wrapper ---------------------------------------------

@pytest.mark.parametrize("stationary", [False, True])
def test_enhance_audio_matches_original_behaviour(tmp_path, noisy_vowel_5db, stationary):
    """Old enhance_audio = float32 read + nr.reduce_noise; the wrapper must give the same array."""
    path = tmp_path / "in.wav"
    sf.write(path, noisy_vowel_5db / np.max(np.abs(noisy_vowel_5db)) * 0.9, SR)
    y, _ = sf.read(path)
    expected = nr.reduce_noise(y=y.astype(np.float32), sr=SR, stationary=stationary)

    out, sr = enhance_audio(str(path), stationary=stationary)
    assert sr == SR
    np.testing.assert_array_equal(out, expected)


def test_enhance_audio_writes_output(tmp_path, noisy_vowel_5db):
    src, dst = tmp_path / "in.wav", tmp_path / "out.wav"
    sf.write(src, noisy_vowel_5db / np.max(np.abs(noisy_vowel_5db)) * 0.9, SR)
    out, _ = enhance_audio(str(src), output_path=str(dst))
    written, sr = sf.read(dst)
    assert sr == SR and len(written) == len(out)
