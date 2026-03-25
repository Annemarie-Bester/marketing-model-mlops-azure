"""
evaluate.py — Model evaluation.

Generates evaluation metrics for the trained pipeline on the held-out test set
and persists results to artifacts/metrics.json.

Metrics chosen for this dataset:
- ROC-AUC  : Primary metric. Threshold-independent, robust to class imbalance.
             Measures ranking quality across all decision thresholds.
- F1 (yes) : F1-score for the minority class (subscription = yes).
             Directly reflects model performance on the class we care about.
- F1 macro : Average F1 across both classes — useful for overall balance check.

Note: Accuracy is intentionally excluded. With 88.4% majority class, a naive
"always predict no" classifier achieves 88.4% accuracy — misleading and useless.
"""

import logging
import os

from sklearn.metrics import (
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)


def evaluate(pipeline: Pipeline, X_test, y_test, config: dict) -> dict:
    """Evaluate the fitted pipeline on the held-out test set.

    Args:
        pipeline: Fitted sklearn Pipeline (preprocessor + classifier).
        X_test: Raw test features (preprocessing applied internally by pipeline).
        y_test: True binary labels for the test set.
        config: Full parsed config dict.

    Returns:
        Dict of metric names to rounded float values.
    """
    y_pred = pipeline.predict(X_test)
    # predict_proba returns [P(class=0), P(class=1)] — we need P(class=1)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    roc_auc = roc_auc_score(y_test, y_prob)
    f1_minority = f1_score(y_test, y_pred, pos_label=1, average="binary")
    f1_macro = f1_score(y_test, y_pred, average="macro")

    metrics = {
        "model_type": config["model"]["type"],
        "test_size": config["model"]["test_size"],
        "roc_auc": round(float(roc_auc), 4),
        "f1_minority_class": round(float(f1_minority), 4),
        "f1_macro": round(float(f1_macro), 4),
    }

    logger.info("ROC-AUC         : %.4f", roc_auc)
    logger.info("F1 (yes/minority): %.4f", f1_minority)
    logger.info("F1 macro        : %.4f", f1_macro)
    logger.info(
        "Classification Report:\n%s",
        classification_report(y_test, y_pred, target_names=["no (0)", "yes (1)"]),
    )

    return metrics


def load_model(config: dict) -> Pipeline:
    """Load a trained pipeline artifact from disk or cloud storage.

    The model path is resolved in this order:
        1. MODEL_PATH env var (allows runtime override without config change)
        2. config["artifacts"]["model_path"] from config.yaml

    Args:
        config: Full parsed config dict.

    Returns:
        Fitted sklearn Pipeline loaded from the artifact path in config.
    """
    from src import storage

    model_path = os.environ.get("MODEL_PATH", config["artifacts"]["model_path"])
    config_dir = os.path.dirname(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    )
    return storage.load_model(model_path, config_dir=config_dir)


def save_metrics(metrics: dict, config: dict) -> str:
    """Persist the metrics dict to artifacts/metrics.json.

    The JSON format is intentionally simple: git-diffable, CI/CD-parseable,
    and readable by stakeholders without tooling. Delegates to the storage
    module so this works on local disk or Azure Blob.

    Args:
        metrics: Dict from evaluate().
        config: Full parsed config dict.

    Returns:
        Path (local) or blob key where the metrics file was saved.
    """
    from src import storage

    config_dir = os.path.dirname(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    )
    return storage.save_json(
        metrics, config["artifacts"]["metrics_path"], config_dir=config_dir
    )
