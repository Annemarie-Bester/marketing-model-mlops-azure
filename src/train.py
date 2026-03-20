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

import joblib
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

# Registry of supported models.
# Adding a new model = adding one entry here + one option in config.yaml.
MODEL_REGISTRY = {
    "logistic_regression": lambda seed: LogisticRegression(
        class_weight="balanced",  # Compensates for 7.6:1 imbalance
        max_iter=1000,            # Increased from default 100 — LR may need more iters post-scaling
        random_state=seed,
        solver="lbfgs",
    ),
    "gradient_boosting": lambda seed: GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=3,
        random_state=seed,
        # Note: does not support class_weight; handles imbalance via residuals
    ),
    "random_forest": lambda seed: RandomForestClassifier(
        class_weight="balanced",
        n_estimators=100,
        random_state=seed,
        n_jobs=-1,
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
    random_state = config["model"]["random_state"]

    if model_type not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model type '{model_type}'. "
            f"Supported types: {list(MODEL_REGISTRY)}"
        )

    model = MODEL_REGISTRY[model_type](random_state)
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

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", model),
    ])

    logger.info(
        "Training '%s' on %d samples...",
        config["model"]["type"], len(X_train),
    )
    pipeline.fit(X_train, y_train)
    logger.info("Training complete.")

    return pipeline


def save_model(pipeline: Pipeline, config: dict) -> str:
    """Persist the trained pipeline to disk as a .pkl artifact.

    The artifact contains both the preprocessor and the classifier,
    making it fully self-contained for serving via the FastAPI service.

    Args:
        pipeline: Fitted sklearn Pipeline from train().
        config: Full parsed config dict.

    Returns:
        Absolute path to the saved artifact.
    """
    # Resolve artifact path relative to repo root (same dir as config.yaml)
    config_dir = os.path.dirname(os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    ))
    artifact_path = os.path.join(config_dir, config["artifacts"]["model_path"])
    os.makedirs(os.path.dirname(artifact_path), exist_ok=True)

    joblib.dump(pipeline, artifact_path)
    logger.info("Model artifact saved: %s", artifact_path)

    return artifact_path
