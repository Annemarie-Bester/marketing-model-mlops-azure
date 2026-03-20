"""
main.py — Single entry point for the ML training pipeline.

Orchestrates the full pipeline in order:
    load data → clean & engineer features → split → build preprocessor
    → train → evaluate → save artifacts

Usage:
    python main.py

All configuration is read from config.yaml in the same directory.
No CLI arguments are needed. To change model type or hyperparameters,
edit config.yaml and re-run.

Outputs:
    artifacts/model.pkl     — Trained sklearn Pipeline (preprocessor + classifier)
    artifacts/metrics.json  — Evaluation metrics (ROC-AUC, F1)
"""

import logging
import os
import sys

# --- Logging setup must happen before any module imports that use logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Ensure src/ is importable when running from the repo root
sys.path.insert(0, os.path.dirname(__file__))

from src.data import load_config, load_data
from src.evaluate import evaluate, save_metrics
from src.features import build_preprocessor, clean_data, split_data
from src.train import save_model, train

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def run_pipeline() -> dict:
    """Execute the full training pipeline and return evaluation metrics.

    Returns:
        Dict of evaluation metrics (roc_auc, f1_minority_class, f1_macro).
    """
    logger.info("=== Bank Marketing ML Pipeline ===")

    # 1. Load configuration
    config = load_config(CONFIG_PATH)
    logger.info("Config: model_type=%s, test_size=%.0f%%",
                config["model"]["type"], config["model"]["test_size"] * 100)

    # 2. Load raw data
    df = load_data(CONFIG_PATH)

    # 3. Clean and engineer features (EDA-driven transforms)
    df_clean = clean_data(df, config)

    # 4. Stratified train/test split
    X_train, X_test, y_train, y_test = split_data(df_clean, config)

    # 5. Build preprocessor — unfitted, will be fit inside pipeline.fit()
    preprocessor = build_preprocessor(X_train)

    # 6. Train: fit the full Pipeline (preprocessor + classifier) on training data
    pipeline = train(X_train, y_train, preprocessor, config)

    # 7. Save model artifact
    model_path = save_model(pipeline, config)

    # 8. Evaluate on held-out test set
    metrics = evaluate(pipeline, X_test, y_test, config)

    # 9. Save metrics
    metrics_path = save_metrics(metrics, config)

    logger.info("=== Pipeline complete ===")
    logger.info("Artifact : %s", model_path)
    logger.info("Metrics  : %s", metrics_path)

    return metrics


if __name__ == "__main__":
    metrics = run_pipeline()

    print("\n" + "=" * 40)
    print(f"  Model     : {metrics['model_type']}")
    print(f"  ROC-AUC   : {metrics['roc_auc']:.4f}")
    print(f"  F1 (yes)  : {metrics['f1_minority_class']:.4f}")
    print(f"  F1 macro  : {metrics['f1_macro']:.4f}")
    print("=" * 40)
