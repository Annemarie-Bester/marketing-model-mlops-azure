"""
config.py — Configuration loader.

Single source of truth for loading config.yaml.
All modules import load_config from here.
"""

import yaml


def load_config(config_path: str) -> dict:
    """Load and parse config.yaml.

    Args:
        config_path: Absolute or relative path to config.yaml.

    Returns:
        Parsed configuration dictionary.
    """
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
