"""
app.py — FastAPI model-serving service.

Loads the trained sklearn pipeline at startup and exposes:
    POST /predict  — score a single customer record
    GET  /health   — liveness/readiness probe for AKS

Operational settings (host, port, workers) are read from environment variables:
    API_HOST        (default: 0.0.0.0)
    API_PORT        (default: 8000)
    UVICORN_WORKERS (default: 1)
The model artifact path is read from config.yaml.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from src.config import get_config_path, load_config
from src.evaluate import load_model
from src.features import clean_data

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))
API_WORKERS = int(os.environ.get("UVICORN_WORKERS", "1"))

logger = logging.getLogger(__name__)

CONFIG_PATH = get_config_path()
config = load_config(CONFIG_PATH)

# --- Pydantic request/response schemas ---


class PredictRequest(BaseModel):
    """Generic feature dictionary for a single record.

    Keys must match the training CSV columns (minus the target column).
    The exact set of features depends on the dataset configured in config.yaml.
    """

    features: Dict[str, Any]

    @field_validator("features")
    @classmethod
    def features_must_not_be_empty(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("features must not be empty")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
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
            ]
        }
    }


class PredictResponse(BaseModel):
    prediction: int
    probability: float
    label: str


class BatchPredictRequest(BaseModel):
    """List of feature dicts for batch scoring.

    Each item in `records` follows the same schema as PredictRequest.features.
    Maximum 1000 records per request to bound latency.
    """

    records: list[Dict[str, Any]]

    @field_validator("records")
    @classmethod
    def records_must_not_be_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("records must not be empty")
        if len(v) > 1000:
            raise ValueError("batch size must not exceed 1000 records")
        return v


class BatchPredictResponse(BaseModel):
    predictions: list[PredictResponse]


# --- API key authentication ---


def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Check X-API-Key header against the API_KEY env var.

    If API_KEY is not set (empty), authentication is skipped —
    allows local development without a key.
    """
    api_key = os.environ.get("API_KEY", "")
    if not api_key:
        return
    if x_api_key != api_key:
        raise HTTPException(
            status_code=401, detail="Invalid or missing API key")


# --- App lifecycle: load model once at startup ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model artifact into app state at startup."""
    logger.info("Loading model artifact...")
    app.state.pipeline = load_model(config)
    logger.info("Model loaded — ready to serve.")
    yield


app = FastAPI(
    title="Bank Marketing Prediction API",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Endpoints ---


@app.get("/health")
def health():
    """Liveness/readiness probe for AKS."""
    pipeline = getattr(app.state, "pipeline", None)
    if pipeline is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "model not loaded"},
        )
    return {"status": "healthy"}


@app.post(
    "/predict/batch",
    response_model=BatchPredictResponse,
    dependencies=[Depends(verify_api_key)],
)
def predict_batch(request: BatchPredictRequest):
    """Score multiple records in a single request.

    Accepts a list of feature dicts and returns a prediction for each.
    Applies the same cleaning pipeline as /predict.
    Maximum 1000 records per call.
    """
    start = time.time()

    df = pd.DataFrame(request.records)
    df_clean = clean_data(df, config)

    pipeline = app.state.pipeline
    preds = pipeline.predict(df_clean).tolist()
    probs = pipeline.predict_proba(df_clean)[:, 1].tolist()

    latency_ms = (time.time() - start) * 1000
    logger.info(
        "Batch prediction: %d records — %.1fms", len(preds), latency_ms
    )

    return BatchPredictResponse(
        predictions=[
            PredictResponse(
                prediction=int(p),
                probability=round(float(prob), 4),
                label="yes" if p == 1 else "no",
            )
            for p, prob in zip(preds, probs)
        ]
    )


@app.post(
    "/predict", response_model=PredictResponse, dependencies=[Depends(verify_api_key)]
)
def predict(request: PredictRequest):
    """Score a single customer record.

    Accepts raw feature values (same schema as the CSV), applies the same
    cleaning pipeline used during training, and returns the prediction.
    """
    start = time.time()

    # Convert request to single-row DataFrame (same shape clean_data expects)
    row = pd.DataFrame([request.features])

    # Apply the same feature engineering as training
    row_clean = clean_data(row, config)

    pipeline = app.state.pipeline
    pred = int(pipeline.predict(row_clean)[0])
    prob = float(pipeline.predict_proba(row_clean)[0, 1])

    latency_ms = (time.time() - start) * 1000
    logger.info("Prediction: %d (prob=%.4f) — %.1fms", pred, prob, latency_ms)

    return PredictResponse(
        prediction=pred,
        probability=round(prob, 4),
        label="yes" if pred == 1 else "no",
    )
