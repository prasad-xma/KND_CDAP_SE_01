"""Tests for component1_robustness.config.load_config."""

from pathlib import Path

import pytest

from component1_robustness.config import DEFAULT_CONFIG_PATH, load_config

REQUIRED_KEYS = {
    "seed", "sample_rate", "min_duration_s", "max_duration_s", "comp1a_pass_db",
    "max_clipping_pct", "min_voice_activity_pct", "enhancement_method",
    "gate_model", "feature_tolerances", "paths", "config_version",
}


def test_default_config_file_exists():
    assert DEFAULT_CONFIG_PATH.is_file()


def test_load_config_returns_dict():
    assert isinstance(load_config(), dict)


def test_required_keys_present():
    missing = REQUIRED_KEYS - load_config().keys()
    assert not missing, f"missing keys: {missing}"


def test_duration_limits():
    cfg = load_config()
    assert 1.5 <= cfg["min_duration_s"] < cfg["max_duration_s"] == 5.0


def test_seed_is_int():
    seed = load_config()["seed"]
    assert isinstance(seed, int) and not isinstance(seed, bool)


def test_feature_tolerances_keys():
    assert set(load_config()["feature_tolerances"]) == {"jitter", "shimmer", "hnr", "mean_f0"}


def test_paths_keys():
    assert {"models", "results", "outputs", "raw_data"} <= load_config()["paths"].keys()


def test_explicit_path_is_used(tmp_path: Path):
    custom = tmp_path / "custom.yaml"
    custom.write_text("seed: 7\n", encoding="utf-8")
    assert load_config(custom) == {"seed": 7}


def test_non_mapping_yaml_rejected(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(bad)


def test_component2_model_path_in_config():
    assert load_config()["paths"]["component2_model"].endswith(".joblib")


def test_resolve_path_relative_is_under_repo_root():
    from component1_robustness.config import REPO_ROOT, resolve_path
    assert resolve_path(load_config(), "results") == REPO_ROOT / "results" / "component1_robustness"


def test_resolve_path_absolute_is_kept(tmp_path):
    from component1_robustness.config import resolve_path
    assert resolve_path({"paths": {"raw_data": str(tmp_path)}}, "raw_data") == tmp_path


def test_resolve_path_real_model_exists():
    from component1_robustness.config import resolve_path
    assert resolve_path(load_config(), "component2_model").is_file()


def test_ddk_feature_tolerances_are_component3_features():
    from component3_ddk.features import FEATURE_NAMES as DDK_FEATURE_NAMES
    tolerances = load_config()["ddk_feature_tolerances"]
    assert tolerances and set(tolerances) <= set(DDK_FEATURE_NAMES)
