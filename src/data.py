"""
data.py — Data loading utilities.

Loads raw data from disk or cloud storage based on configuration
and the STORAGE_BACKEND environment variable.
"""

import logging
import os

import pandas as pd

from src import storage

logger = logging.getLogger(__name__)


def load_data(config: dict, config_dir: str) -> pd.DataFrame:
    """Load raw data from the path specified in config.

    Args:
        config: Parsed configuration dictionary.
        config_dir: Directory containing config.yaml (used to resolve relative paths).

    Returns:
        Raw DataFrame with no transformations applied.
    """
    data_cfg = config["data"]

    raw_path = data_cfg["raw_path"]
    separator = data_cfg.get("separator", ",")
    index_col = data_cfg.get("index_col", None)

    logger.info("Loading data from: %s", raw_path)
    df = storage.read_csv(
        raw_path, config_dir=config_dir, sep=separator, index_col=index_col
    )
    logger.info("Loaded %d rows, %d columns", df.shape[0], df.shape[1])

    return df
