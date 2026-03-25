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
    response = client.post("/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    assert response.status_code == 200


def test_predict_response_shape(client):
    response = client.post("/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    data = response.json()
    assert "prediction" in data
    assert "probability" in data
    assert "label" in data


def test_predict_values(client):
    response = client.post("/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    data = response.json()
    assert data["prediction"] in (0, 1)
    assert 0.0 <= data["probability"] <= 1.0
    assert data["label"] in ("yes", "no")


def test_predict_label_matches_prediction(client):
    response = client.post("/predict", json=SAMPLE_REQUEST, headers=AUTH_HEADER)
    data = response.json()
    expected_label = "yes" if data["prediction"] == 1 else "no"
    assert data["label"] == expected_label


def test_predict_missing_field(client):
    """Omitting a required field should return 422."""
    incomplete = {k: v for k, v in SAMPLE_REQUEST.items() if k != "age"}
    response = client.post("/predict", json=incomplete, headers=AUTH_HEADER)
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
