"""
test_evaluate.py — Unit tests for src/evaluate.py.

Covers:
- evaluate(): metric dict keys, types, and value ranges on synthetic data.
- load_model(): delegates to storage.load_model with the correct path.
- save_metrics(): delegates to storage.save_json with the correct args.
"""

from unittest.mock import MagicMock

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from src.evaluate import evaluate, load_model, save_metrics


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_pipeline():
    """Return a tiny fitted pipeline on linearly separable synthetic data."""
    X = [[0.0], [0.1], [0.9], [1.0]]
    y = [0, 0, 1, 1]
    pipe = Pipeline([
        ("pre", FunctionTransformer(lambda x: x)),
        ("clf", LogisticRegression(random_state=0, max_iter=1000)),
    ])
    pipe.fit(X, y)
    return pipe


_CONFIG = {
    "model": {"type": "logistic_regression", "test_size": 0.2},
    "artifacts": {
        "model_path": "artifacts/model.pkl",
        "metrics_path": "artifacts/metrics.json",
    },
}


# ── Tests: evaluate() ────────────────────────────────────────────────────────


def test_evaluate_returns_required_keys():
    pipe = _make_pipeline()
    metrics = evaluate(pipe, [[0.05], [0.95]], [0, 1], _CONFIG)
    for key in ("model_type", "test_size", "roc_auc", "f1_minority_class", "f1_macro"):
        assert key in metrics, f"Missing key: {key}"


def test_evaluate_metric_types_and_ranges():
    pipe = _make_pipeline()
    metrics = evaluate(pipe, [[0.05], [0.95]], [0, 1], _CONFIG)
    assert isinstance(metrics["roc_auc"], float)
    assert 0.0 <= metrics["roc_auc"] <= 1.0
    assert 0.0 <= metrics["f1_minority_class"] <= 1.0
    assert 0.0 <= metrics["f1_macro"] <= 1.0


def test_evaluate_model_type_and_test_size_from_config():
    pipe = _make_pipeline()
    metrics = evaluate(pipe, [[0.05], [0.95]], [0, 1], _CONFIG)
    assert metrics["model_type"] == "logistic_regression"
    assert metrics["test_size"] == 0.2


def test_evaluate_metrics_are_rounded():
    """Returned float values should be rounded to 4 decimal places."""
    pipe = _make_pipeline()
    metrics = evaluate(pipe, [[0.05], [0.95]], [0, 1], _CONFIG)
    for key in ("roc_auc", "f1_minority_class", "f1_macro"):
        val = metrics[key]
        assert round(val, 4) == val, f"{key} not rounded to 4dp: {val}"


# ── Tests: load_model() ──────────────────────────────────────────────────────


def test_load_model_delegates_to_storage(monkeypatch):
    import src.storage as storage_mod

    mock_pipeline = MagicMock()
    mock_load = MagicMock(return_value=mock_pipeline)
    monkeypatch.setattr(storage_mod, "load_model", mock_load)

    result = load_model(_CONFIG)
    assert result is mock_pipeline
    mock_load.assert_called_once()
    # First positional arg should be the model path from config
    assert mock_load.call_args[0][0] == "artifacts/model.pkl"


# ── Tests: save_metrics() ────────────────────────────────────────────────────


def test_save_metrics_delegates_to_storage(monkeypatch):
    import src.storage as storage_mod

    mock_save = MagicMock(return_value="artifacts/metrics.json")
    monkeypatch.setattr(storage_mod, "save_json", mock_save)

    metrics = {"roc_auc": 0.9, "f1_macro": 0.8}
    result = save_metrics(metrics, _CONFIG)

    assert result == "artifacts/metrics.json"
    mock_save.assert_called_once()
    # First arg is the metrics dict, second is the path
    assert mock_save.call_args[0][0] == metrics
    assert mock_save.call_args[0][1] == "artifacts/metrics.json"
