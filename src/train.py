"""
train.py — Model training.

Builds a full sklearn Pipeline (preprocessor + classifier), trains it on
training data, and saves the artifact to the path in config.yaml.

Design decisions:
- The preprocessor and classifier are wrapped in a single sklearn Pipeline.
  This means the saved artifact self-contains all preprocessing steps.
  At inference time (API), loading the .pkl and calling .predict() is all
  that's needed — no separate preprocessing code path to maintain.
- class_weight='balanced' is used for LR and RF to handle the 7.6:1 class
  imbalance without resampling (simpler and sufficient for a baseline).
- GradientBoosting handles imbalance implicitly through sequential residual
  learning; class_weight is not supported by that estimator.
- Random state is sourced from config for full reproducibility.
"""

import logging
import os

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.config import get_config_path

logger = logging.getLogger(__name__)

# Registry of supported models.
# Only logistic regression is supported in this repo (per project requirement).
MODEL_REGISTRY = {
    "logistic_regression": lambda cfg: LogisticRegression(
        class_weight=cfg["model"].get("class_weight", None),
        max_iter=cfg["model"].get("max_iter", 1000),
        random_state=cfg["model"].get("random_state", None),
        solver=cfg["model"].get("solver", "lbfgs"),
    ),
}


def get_model(config: dict):
    """Instantiate the model specified in config.yaml.

    Args:
        config: Full parsed config dict.

    Returns:
        Unfitted sklearn estimator.

    Raises:
        ValueError: If model type is not in MODEL_REGISTRY.
    """
    model_type = config["model"]["type"]

    # Enforce single-model policy: only logistic_regression is supported.
    if model_type != "logistic_regression":
        raise ValueError(
            "Only 'logistic_regression' is supported in this project. "
            "Please set model.type to 'logistic_regression' in config.yaml."
        )

    model = MODEL_REGISTRY["logistic_regression"](config)
    logger.info("Instantiated model: %s", model_type)
    return model


def train(X_train, y_train, preprocessor, config: dict) -> Pipeline:
    """Build a full sklearn Pipeline and fit it on the training data.

    The pipeline order is: preprocessor → classifier.
    Fitting in this order ensures the preprocessor (imputers, scalers, encoders)
    is fit only on X_train, preventing test-set leakage.

    Args:
        X_train: Raw training features (before preprocessing).
        y_train: Binary training labels (0/1).
        preprocessor: Unfitted ColumnTransformer from build_preprocessor().
        config: Full parsed config dict.

    Returns:
        Fitted sklearn Pipeline (preprocessor + classifier).
    """
    model = get_model(config)

    pipeline = Pipeline(
        [
            ("preprocessor", preprocessor),
            ("classifier", model),
        ]
    )

    logger.info(
        "Training '%s' on %d samples...",
        config["model"]["type"],
        len(X_train),
    )
    pipeline.fit(X_train, y_train)
    logger.info("Training complete.")

    return pipeline


def save_model(pipeline: Pipeline, config: dict) -> str:
    """Persist the trained pipeline as a .pkl artifact.

    The artifact contains both the preprocessor and the classifier,
    making it fully self-contained for serving via the FastAPI service.
    Delegates to the storage module so this works on local disk or Azure Blob.

    Args:
        pipeline: Fitted sklearn Pipeline from train().
        config: Full parsed config dict.

    Returns:
        Path (local) or blob key where the artifact was saved.
    """
    from src import storage

    config_dir = os.path.dirname(get_config_path())
    return storage.save_model(
        pipeline, config["artifacts"]["model_path"], config_dir=config_dir
    )
