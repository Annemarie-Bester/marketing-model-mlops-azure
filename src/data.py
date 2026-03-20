"""
data.py — Data loading utilities.

Reads configuration from config.yaml and returns a clean DataFrame.
"""

import logging
import os

import pandas as pd
import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_data(config_path: str) -> pd.DataFrame:
    """Load raw data from the path specified in config.yaml.

    Args:
        config_path: Path to config.yaml (relative to project root or absolute).

    Returns:
        Raw DataFrame with no transformations applied.
    """
    config = load_config(config_path)
    data_cfg = config["data"]

    # Resolve raw_path relative to the config file's directory (not CWD),
    # so the same config works whether called from the repo root, notebooks/, or anywhere else.
    config_dir = os.path.dirname(os.path.abspath(config_path))
    raw_path = os.path.join(config_dir, data_cfg["raw_path"])
    separator = data_cfg.get("separator", ",")
    index_col = data_cfg.get("index_col", None)

    logger.info("Loading data from: %s", raw_path)
    df = pd.read_csv(raw_path, sep=separator, index_col=index_col)
    logger.info("Loaded %d rows, %d columns", df.shape[0], df.shape[1])

    return df
