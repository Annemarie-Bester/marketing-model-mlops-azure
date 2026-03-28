"""
test_config.py — Tests for src/config.py
"""

import os
import textwrap

import pytest

from src.config import get_config_path, load_config


def test_get_config_path_returns_existing_file():
    """get_config_path() must resolve to the actual config.yaml in the repo."""
    path = get_config_path()
    assert os.path.isabs(path), "Expected an absolute path"
    assert path.endswith("config.yaml")
    assert os.path.isfile(path), f"config.yaml not found at: {path}"


def test_load_config_returns_dict(tmp_path):
    """load_config should parse valid YAML and return a dict."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""\
        model:
          type: logistic_regression
          test_size: 0.2
    """))
    result = load_config(str(cfg_file))
    assert isinstance(result, dict)


def test_load_config_required_keys(tmp_path):
    """Parsed config must contain all top-level sections expected by the pipeline."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""\
        data:
          raw_path: data/raw/bank_marketing_data.csv
          separator: ";"
          index_col: 0
        features:
          age_cap: 100
          log_transform_cols: [duration, campaign]
          signed_log_cols: [balance]
          drop_cols: [post_campaign_action]
        model:
          target_column: target
          type: logistic_regression
          test_size: 0.2
          random_state: 42
        artifacts:
          model_path: artifacts/model.pkl
          metrics_path: artifacts/metrics.json
        api:
          host: 0.0.0.0
          port: 8000
          workers: 1
    """))
    result = load_config(str(cfg_file))
    for key in ("data", "features", "model", "artifacts", "api"):
        assert key in result, f"Missing top-level key: '{key}'"


def test_load_config_values(tmp_path):
    """Values are parsed correctly from YAML."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""\
        model:
          type: gradient_boosting
          test_size: 0.25
          random_state: 99
    """))
    result = load_config(str(cfg_file))
    assert result["model"]["type"] == "gradient_boosting"
    assert result["model"]["test_size"] == 0.25
    assert result["model"]["random_state"] == 99


def test_load_config_missing_file():
    """load_config should raise FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.yaml")
