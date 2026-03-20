"""
main.py — Single entry point for the ML pipeline.

Commands:
    python main.py train      — Run the full training pipeline
    python main.py predict    — Batch predict using a trained model

All configuration is read from config.yaml. No hidden parameters.
"""

from src.train import save_model, train
from src.features import build_preprocessor, clean_data, split_data
from src.evaluate import evaluate, load_model, save_metrics
from src.data import load_data
from src.config import load_config
import argparse
import logging
import os
import sys

import pandas as pd

# --- Logging setup must happen before any module imports that use logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Ensure src/ is importable when running from the repo root
sys.path.insert(0, os.path.dirname(__file__))


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
CONFIG_DIR = os.path.dirname(os.path.abspath(CONFIG_PATH))


def cmd_train() -> dict:
    """Execute the full training pipeline and return evaluation metrics."""
    logger.info("=== Bank Marketing ML Pipeline — Train ===")

    # 1. Load configuration
    config = load_config(CONFIG_PATH)
    logger.info("Config: model_type=%s, test_size=%.0f%%",
                config["model"]["type"], config["model"]["test_size"] * 100)

    # 2. Load raw data
    df = load_data(config, CONFIG_DIR)

    # 3. Clean and engineer features
    df_clean = clean_data(df, config)

    # 4. Stratified train/test split
    X_train, X_test, y_train, y_test = split_data(df_clean, config)

    # 5. Build preprocessor (unfitted)
    preprocessor = build_preprocessor(X_train)

    # 6. Train pipeline (preprocessor + classifier)
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

    print("\n" + "=" * 40)
    print(f"  Model     : {metrics['model_type']}")
    print(f"  ROC-AUC   : {metrics['roc_auc']:.4f}")
    print(f"  F1 (yes)  : {metrics['f1_minority_class']:.4f}")
    print(f"  F1 macro  : {metrics['f1_macro']:.4f}")
    print("=" * 40)

    return metrics


def cmd_predict(input_path: str, output_path: str | None) -> None:
    """Load a trained model and generate predictions on new data."""
    logger.info("=== Bank Marketing ML Pipeline — Predict ===")

    config = load_config(CONFIG_PATH)

    # Load trained model artifact
    pipeline = load_model(config)

    # Load and clean input data (same transforms as training, minus target encoding)
    data_cfg = config["data"]
    logger.info("Reading input data from: %s", input_path)
    df = pd.read_csv(
        input_path,
        sep=data_cfg.get("separator", ","),
        index_col=data_cfg.get("index_col", None),
    )
    logger.info("Loaded %d rows", len(df))

    df_clean = clean_data(df, config)

    # Generate predictions
    predictions = pipeline.predict(df_clean)
    probabilities = pipeline.predict_proba(df_clean)[:, 1]

    result = df_clean.copy()
    result["prediction"] = predictions
    result["probability"] = probabilities.round(4)

    # Output results
    if output_path:
        result.to_csv(output_path)
        logger.info("Predictions saved to: %s", output_path)
    else:
        print(result[["prediction", "probability"]].to_string())

    logger.info("=== Predict complete — %d rows scored ===", len(result))


def main():
    parser = argparse.ArgumentParser(
        description="Bank Marketing ML Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:"
               "  python main.py train"
               "  python main.py predict --input data/raw/bank_marketing_data.csv\n"
               "  python main.py predict --input data/raw/bank_marketing_data.csv --output predictions.csv",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- train ---
    subparsers.add_parser("train", help="Run the full training pipeline")

    # --- predict ---
    predict_parser = subparsers.add_parser(
        "predict", help="Batch predict using a trained model")
    predict_parser.add_argument(
        "--input", required=True, help="Path to input CSV file"
    )
    predict_parser.add_argument(
        "--output", default=None, help="Path to output CSV (default: print to stdout)"
    )

    args = parser.parse_args()

    if args.command == "train":
        cmd_train()
    elif args.command == "predict":
        cmd_predict(args.input, args.output)


if __name__ == "__main__":
    main()
