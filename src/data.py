"""
data.py — Data loading utilities.

Loads raw data from disk based on configuration.
"""

import logging
import os

import pandas as pd

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

    raw_path = os.path.join(config_dir, data_cfg["raw_path"])
    separator = data_cfg.get("separator", ",")
    index_col = data_cfg.get("index_col", None)

    logger.info("Loading data from: %s", raw_path)
    df = pd.read_csv(raw_path, sep=separator, index_col=index_col)
    logger.info("Loaded %d rows, %d columns", df.shape[0], df.shape[1])

    return df
