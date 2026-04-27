"""
conftest.py — Shared pytest fixtures.

Fixtures here are available to all test modules automatically.
All fixtures use in-memory data — no disk I/O, no dependency on
the real dataset being present.
"""

# Ensure the repository root is on sys.path so tests can import `src`.
import pytest
import pandas as pd
import textwrap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def config():
    """Minimal config dict mirroring config.yaml structure."""
    return {
        "data": {
            "raw_path": "data/raw/bank_marketing_data.csv",
            "separator": ";",
            "index_col": 0,
        },
        "features": {
            "age_cap": 100,
            "log_transform_cols": ["duration", "campaign"],
            "signed_log_cols": ["balance"],
            "drop_cols": ["post_campaign_action"],
        },
        "model": {
            "target_column": "target",
            "type": "logistic_regression",
            "test_size": 0.2,
            "random_state": 42,
        },
        "artifacts": {
            "model_path": "artifacts/model.pkl",
            "metrics_path": "artifacts/metrics.json",
        },
    }


@pytest.fixture
def raw_df():
    """Small raw DataFrame with the same columns as the real dataset.

    Includes edge cases exercised by clean_data():
    - One row with age > 100 (should be capped)
    - One row with pdays == -1 (never contacted → contacted_before = 0)
    - One row with pdays > 0  (was contacted → contacted_before = 1)
    - Negative balance (tests signed-log transform)
    - post_campaign_action column (should be dropped)
    - target as 'yes'/'no' strings (should be encoded to 1/0)
    """
    return pd.DataFrame(
        {
            "age": [30, 150, 45],  # row 1: age > 100 → capped
            "job": ["admin.", "blue-collar", "technician"],
            "marital": ["married", "single", "divorced"],
            "education": ["secondary", "primary", "tertiary"],
            "default": ["no", "no", "yes"],
            "balance": [1000.0, -500.0, 0.0],  # negative tests signed-log
            "housing": ["yes", "no", "yes"],
            "loan": ["no", "yes", "no"],
            "contact": ["cellular", "unknown", "telephone"],
            "day": [5, 12, 20],
            "month": ["jan", "feb", "mar"],
            "duration": [100, 200, 50],
            "campaign": [1, 3, 2],
            "pdays": [-1, 180, -1],  # -1 → contacted_before=0; 180 → 1
            "previous": [0, 2, 0],
            "poutcome": ["unknown", "success", "failure"],
            "target": ["no", "yes", "no"],
            # leakage column — must be dropped
            "post_campaign_action": [0, 1, 0],
        }
    )
