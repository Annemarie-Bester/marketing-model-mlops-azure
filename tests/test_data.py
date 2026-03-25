"""
test_data.py — Tests for src/data.py
"""

import pandas as pd
import pytest

from src.data import load_data


def test_load_data_returns_dataframe(tmp_path, config):
    """load_data should return a DataFrame when given a valid CSV."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(";age;job;target\n" "0;30;admin.;no\n" "1;45;technician;yes\n")
    config["data"]["raw_path"] = "test.csv"
    config["data"]["separator"] = ";"
    config["data"]["index_col"] = 0

    result = load_data(config, config_dir=str(tmp_path))
    assert isinstance(result, pd.DataFrame)


def test_load_data_row_count(tmp_path, config):
    """Loaded DataFrame should have the same number of rows as the CSV."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        ";age;job;target\n"
        "0;30;admin.;no\n"
        "1;45;technician;yes\n"
        "2;55;blue-collar;no\n"
    )
    config["data"]["raw_path"] = "test.csv"
    config["data"]["separator"] = ";"
    config["data"]["index_col"] = 0

    result = load_data(config, config_dir=str(tmp_path))
    assert len(result) == 3


def test_load_data_columns(tmp_path, config):
    """Loaded DataFrame should contain the expected column names."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(";age;job;target\n" "0;30;admin.;no\n")
    config["data"]["raw_path"] = "test.csv"
    config["data"]["separator"] = ";"
    config["data"]["index_col"] = 0

    result = load_data(config, config_dir=str(tmp_path))
    assert "age" in result.columns
    assert "job" in result.columns
    assert "target" in result.columns


def test_load_data_missing_file(tmp_path, config):
    """load_data should raise FileNotFoundError when the CSV does not exist."""
    config["data"]["raw_path"] = "nonexistent.csv"
    with pytest.raises(FileNotFoundError):
        load_data(config, config_dir=str(tmp_path))
