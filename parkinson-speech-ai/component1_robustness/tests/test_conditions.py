"""Tests for the shared CONDITIONS list, condition_rng() and degrade()."""

import numpy as np
import pytest

from component1_robustness import evaluate_enhancement, experiment
from component1_robustness.conditions import CONDITIONS, N_PER_CLASS, condition_rng, degrade, sample_clean_files
from component1_robustness.config import load_config

SAMPLING_SCRIPTS = [experiment, evaluate_enhancement]


def test_condition_names_unique():
    names = [name for name, _ in CONDITIONS]
    assert len(names) == len(set(names))


def test_clean_condition_present():
    assert ("clean", None) in CONDITIONS


def test_degrade_none_returns_input_unchanged(tone, sr):
    out = degrade(tone, sr, None, rng=np.random.default_rng(0))
    assert out is tone
    np.testing.assert_array_equal(out, tone)


@pytest.mark.parametrize("name,spec", [c for c in CONDITIONS if c[1] is not None])
def test_degrade_every_condition_keeps_length(tone, sr, name, spec):
    out = degrade(tone, sr, spec, rng=np.random.default_rng(0))
    assert out.shape == tone.shape
    assert np.all(np.isfinite(out))


def test_degrade_same_seed_same_output(tone, sr):
    a = degrade(tone, sr, ("noise", 5), rng=np.random.default_rng(42))
    b = degrade(tone, sr, ("noise", 5), rng=np.random.default_rng(42))
    np.testing.assert_array_equal(a, b)


def test_degrade_rng_is_required(tone, sr):
    with pytest.raises(TypeError):
        degrade(tone, sr, ("noise", 5))


def test_degrade_unknown_kind_raises(tone, sr):
    with pytest.raises(ValueError):
        degrade(tone, sr, ("telephone", 1), rng=np.random.default_rng(0))


# --- condition_rng -----------------------------------------------------------

def _first_draws(rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal(5)


def test_condition_rng_same_inputs_same_stream():
    seed = load_config()["seed"]
    a = _first_draws(condition_rng(seed, "clip_001.wav", "noise_snr_5db"))
    b = _first_draws(condition_rng(seed, "clip_001.wav", "noise_snr_5db"))
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("other", [
    (43, "clip_001.wav", "noise_snr_5db"),   # different seed
    (42, "clip_002.wav", "noise_snr_5db"),   # different clip
    (42, "clip_001.wav", "noise_snr_0db"),   # different condition
])
def test_condition_rng_changes_with_any_input(other):
    base = _first_draws(condition_rng(42, "clip_001.wav", "noise_snr_5db"))
    assert not np.array_equal(base, _first_draws(condition_rng(*other)))


def test_condition_rng_gives_same_degraded_audio_in_every_script(tone, sr):
    """experiment / evaluate_enhancement / labels all derive noise the same way."""
    seed = load_config()["seed"]
    outputs = [degrade(tone, sr, ("noise", 5), condition_rng(seed, "a.wav", "noise_snr_5db")) for _ in range(3)]
    np.testing.assert_array_equal(outputs[0], outputs[1])
    np.testing.assert_array_equal(outputs[0], outputs[2])


# --- Scripts use the shared list and the config seed -------------------------

def test_scripts_share_one_conditions_list():
    assert experiment.CONDITIONS is CONDITIONS


def test_enhancement_conditions_are_subset_of_shared_list():
    shared = dict(CONDITIONS)
    for name, spec in evaluate_enhancement.ENHANCEMENT_CONDITIONS:
        assert shared[name] == spec
    assert "clean" not in dict(evaluate_enhancement.ENHANCEMENT_CONDITIONS)


@pytest.mark.parametrize("module", SAMPLING_SCRIPTS, ids=lambda m: m.__name__.split(".")[-1])
def test_no_hardcoded_random_state(module):
    assert not hasattr(module, "RANDOM_STATE")


@pytest.fixture
def fake_raw_dir(tmp_path):
    """Empty placeholder .wav files: sample_clean_files only globs names."""
    for group in ("PD_AH", "HC_AH"):
        (tmp_path / group).mkdir()
        for i in range(20):
            (tmp_path / group / f"{group}_{i:02d}.wav").touch()
    return tmp_path


def _names(sample) -> list[str]:
    return [str(item[0] if isinstance(item, tuple) else item) for item in sample]


def test_sample_clean_files_seeded(fake_raw_dir):
    a = _names(sample_clean_files(42, fake_raw_dir))
    b = _names(sample_clean_files(42, fake_raw_dir))
    c = _names(sample_clean_files(7, fake_raw_dir))
    assert a == b
    assert a != c
    assert len(a) == 2 * N_PER_CLASS


@pytest.mark.parametrize("module", SAMPLING_SCRIPTS, ids=lambda m: m.__name__.split(".")[-1])
def test_scripts_share_one_sampler(module):
    """Both studies use the same sampler, so they test the same recordings."""
    assert module.sample_clean_files is sample_clean_files
