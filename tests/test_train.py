import importlib
from unittest.mock import MagicMock

import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import FunctionTransformer

from src.train import get_model, train, save_model


def test_get_model_accepts_logistic_regression():
    cfg = {
        "model": {
            "type": "logistic_regression",
            "random_state": 0,
            "class_weight": "balanced",
            "max_iter": 123,
            "solver": "lbfgs",
        }
    }

    model = get_model(cfg)
    assert isinstance(model, LogisticRegression)
    assert model.max_iter == 123
    assert model.random_state == 0


def test_get_model_rejects_other_types():
    cfg = {"model": {"type": "random_forest"}}
    with pytest.raises(ValueError):
        get_model(cfg)


def test_train_builds_and_fits_pipeline():
    # Simple synthetic dataset; preprocessor is identity to keep test focused.
    X_train = [[0.1], [0.2], [1.0], [1.2]]
    y_train = [0, 0, 1, 1]

    preprocessor = FunctionTransformer(lambda X: X)

    cfg = {
        "model": {
            "type": "logistic_regression",
            "random_state": 42,
            "max_iter": 1000,
            "class_weight": "balanced",
            "solver": "lbfgs",
        },
        "artifacts": {"model_path": "artifacts/model.pkl"},
    }

    pipeline = train(X_train, y_train, preprocessor, cfg)

    # Pipeline should expose predict and contain logistic regression classifier.
    assert hasattr(pipeline, "predict")
    assert "classifier" in pipeline.named_steps
    assert isinstance(pipeline.named_steps["classifier"], LogisticRegression)

    preds = pipeline.predict([[0.1], [1.5]])
    assert len(preds) == 2


def test_save_model_calls_storage(monkeypatch):
    # Create a tiny fitted pipeline by training on synthetic data.
    X_train = [[0.0], [1.0]]
    y_train = [0, 1]
    preprocessor = FunctionTransformer(lambda X: X)
    cfg = {
        "model": {"type": "logistic_regression", "random_state": 0},
        "artifacts": {"model_path": "artifacts/model.pkl"},
    }

    pipeline = train(X_train, y_train, preprocessor, cfg)

    # Monkeypatch src.storage.save_model to avoid IO and verify call.
    import src.storage as storage_mod

    mock_save = MagicMock(return_value="mocked://path/to/model.pkl")
    monkeypatch.setattr(storage_mod, "save_model", mock_save)

    result = save_model(pipeline, cfg)
    assert result == "mocked://path/to/model.pkl"
    mock_save.assert_called_once()
