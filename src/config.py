"""
config.py — Configuration loader.

Single source of truth for config.yaml path resolution and loading.
All modules import get_config_path and load_config from here.
"""

import os

import yaml


def get_config_path() -> str:
    """Return the absolute path to config.yaml at the repo root.

    Resolves relative to this file's location so it works regardless
    of the current working directory (local, Docker, CI).

    Returns:
        Absolute path string to config.yaml.
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))


def load_config(config_path: str) -> dict:
    """Load and parse config.yaml.

    Args:
        config_path: Absolute or relative path to config.yaml.

    Returns:
        Parsed configuration dictionary.
    """
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
