"""
test_api.py — Tests for the FastAPI prediction service.

Uses FastAPI's TestClient (no running server required).
Requires a trained model artifact at artifacts/model.pkl.
"""

from src.api.app import app
import os

import pytest
from fastapi.testclient import TestClient

# Set API_KEY before importing app so the dependency uses it
TEST_API_KEY = "test-key-for-pytest"
os.environ["API_KEY"] = TEST_API_KEY


AUTH_HEADER = {"X-API-Key": TEST_API_KEY}

SAMPLE_REQUEST = {
    "features": {
        "age": 35,
        "job": "management",
        "marital": "married",
        "education": "tertiary",
        "default": "no",
        "balance": 1500.0,
        "housing": "yes",
        "loan": "no",
        "contact": "cellular",
        "day": 15,
        "month": "may",
        "duration": 250.0,
        "campaign": 1,
        "pdays": -1,
        "previous": 0,
        "poutcome": "unknown",
    }
}


@pytest.fixture(scope="module")
def client():
    """TestClient as context manager so lifespan (model loading) runs."""
    with TestClient(app) as c:
        yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_predict_returns_200(client):
    response = client.post(
        "/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    assert response.status_code == 200


def test_predict_response_shape(client):
    response = client.post(
        "/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    data = response.json()
    assert "prediction" in data
    assert "probability" in data
    assert "label" in data


def test_predict_values(client):
    response = client.post(
        "/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    data = response.json()
    assert data["prediction"] in (0, 1)
    assert 0.0 <= data["probability"] <= 1.0
    assert data["label"] in ("yes", "no")


def test_predict_label_matches_prediction(client):
    response = client.post(
        "/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    data = response.json()
    expected_label = "yes" if data["prediction"] == 1 else "no"
    assert data["label"] == expected_label


def test_predict_empty_features(client):
    """Empty features dict should return 422."""
    response = client.post(
        "/predict", json={"features": {}}, headers=AUTH_HEADER)
    assert response.status_code == 422


def test_predict_missing_api_key(client):
    """Request without X-API-Key header should return 401."""
    response = client.post("/predict", json=SAMPLE_REQUEST)
    assert response.status_code == 401


def test_predict_wrong_api_key(client):
    """Request with incorrect API key should return 401."""
    response = client.post(
        "/predict", json=SAMPLE_REQUEST, headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401


def test_health_model_not_loaded():
    """503 is returned when the pipeline is not in app state (model load failed)."""
    with TestClient(app) as c:
        original = app.state.pipeline
        try:
            app.state.pipeline = None
            response = c.get("/health")
            assert response.status_code == 503
            body = response.json()
            assert body["status"] == "unhealthy"
            assert "model not loaded" in body["reason"]
        finally:
            app.state.pipeline = original


# ── Batch prediction tests ─────────────────────────────────────────────────


SAMPLE_FEATURES = SAMPLE_REQUEST["features"]

BATCH_REQUEST = {
    "records": [
        SAMPLE_FEATURES,
        {**SAMPLE_FEATURES, "age": 22, "job": "student", "balance": 100.0},
        {**SAMPLE_FEATURES, "age": 55, "job": "retired", "balance": -200.0},
    ]
}


def test_batch_predict_returns_200(client):
    response = client.post(
        "/predict/batch", json=BATCH_REQUEST, headers=AUTH_HEADER
    )
    assert response.status_code == 200


def test_batch_predict_response_length(client):
    """Response must contain one prediction per input record."""
    response = client.post(
        "/predict/batch", json=BATCH_REQUEST, headers=AUTH_HEADER
    )
    data = response.json()
    assert len(data["predictions"]) == len(BATCH_REQUEST["records"])


def test_batch_predict_response_shape(client):
    """Each prediction must have prediction, probability, and label fields."""
    response = client.post(
        "/predict/batch", json=BATCH_REQUEST, headers=AUTH_HEADER
    )
    for item in response.json()["predictions"]:
        assert "prediction" in item
        assert "probability" in item
        assert "label" in item


def test_batch_predict_values(client):
    """Each prediction must have valid binary outputs and probability in [0,1]."""
    response = client.post(
        "/predict/batch", json=BATCH_REQUEST, headers=AUTH_HEADER
    )
    for item in response.json()["predictions"]:
        assert item["prediction"] in (0, 1)
        assert 0.0 <= item["probability"] <= 1.0
        assert item["label"] in ("yes", "no")


def test_batch_predict_label_matches_prediction(client):
    response = client.post(
        "/predict/batch", json=BATCH_REQUEST, headers=AUTH_HEADER
    )
    for item in response.json()["predictions"]:
        expected = "yes" if item["prediction"] == 1 else "no"
        assert item["label"] == expected


def test_batch_predict_empty_records(client):
    """Empty records list should return 422."""
    response = client.post(
        "/predict/batch", json={"records": []}, headers=AUTH_HEADER
    )
    assert response.status_code == 422


def test_batch_predict_exceeds_limit(client):
    """More than 1000 records should return 422."""
    big_batch = {"records": [SAMPLE_FEATURES] * 1001}
    response = client.post(
        "/predict/batch", json=big_batch, headers=AUTH_HEADER
    )
    assert response.status_code == 422


def test_batch_predict_requires_api_key(client):
    """Batch endpoint must also enforce API key auth."""
    response = client.post("/predict/batch", json=BATCH_REQUEST)
    assert response.status_code == 401


def test_batch_predict_single_record(client):
    """A batch of one record must work and return one prediction."""
    response = client.post(
        "/predict/batch",
        json={"records": [SAMPLE_FEATURES]},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 200
    assert len(response.json()["predictions"]) == 1
