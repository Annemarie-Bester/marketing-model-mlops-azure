"""
storage.py — Storage abstraction for local and cloud I/O.

Supports two backends controlled by the STORAGE_BACKEND environment variable:
    - 'local'      (default) — read/write from local filesystem
    - 'azure_blob' — read/write from Azure Blob Storage

Azure Blob configuration (required when STORAGE_BACKEND=azure_blob):
    AZURE_STORAGE_CONNECTION_STRING — connection string (local dev / CI)
    — or —
    AZURE_STORAGE_ACCOUNT_NAME     — account name (AKS with managed identity)

    AZURE_STORAGE_CONTAINER        — blob container name
"""

import io
import json
import logging
import os

import joblib
import pandas as pd

logger = logging.getLogger(__name__)


def get_backend() -> str:
    """Return the active storage backend from STORAGE_BACKEND env var."""
    return os.environ.get("STORAGE_BACKEND", "local")


def _get_blob_service_client():
    """Create a BlobServiceClient using connection string or managed identity.

    Deferred import — azure packages are only loaded when the blob backend
    is active. Local mode never touches these imports.
    """
    from azure.storage.blob import BlobServiceClient

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)

    account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    if not account_name:
        raise EnvironmentError(
            "STORAGE_BACKEND=azure_blob requires either "
            "AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_NAME"
        )

    from azure.identity import DefaultAzureCredential

    return BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=DefaultAzureCredential(),
    )


def _get_container_name() -> str:
    """Return the blob container name from AZURE_STORAGE_CONTAINER env var."""
    name = os.environ.get("AZURE_STORAGE_CONTAINER")
    if not name:
        raise EnvironmentError(
            "STORAGE_BACKEND=azure_blob requires AZURE_STORAGE_CONTAINER"
        )
    return name


def _resolve_local(path: str, config_dir: str) -> str:
    """Resolve a config-relative path against config_dir for local storage."""
    if os.path.isabs(path):
        return path
    return os.path.join(config_dir, path)


def _resolve_blob_path(path: str) -> str:
    """Prepend MODEL_BLOB_PREFIX to the blob path if set.

    Allows environment-based model path separation:
        MODEL_BLOB_PREFIX=staging   → staging/artifacts/model.pkl
        MODEL_BLOB_PREFIX=production → production/artifacts/model.pkl
        (unset)                     → artifacts/model.pkl (as-is)
    """
    prefix = os.environ.get("MODEL_BLOB_PREFIX", "")
    if prefix:
        return f"{prefix}/{path}"
    return path


# --- Public API ---


def read_csv(path: str, config_dir: str = "", **kwargs) -> pd.DataFrame:
    """Read a CSV file from local filesystem or Azure Blob Storage."""
    backend = get_backend()

    if backend == "local":
        full_path = _resolve_local(path, config_dir)
        logger.info("Reading CSV (local): %s", full_path)
        return pd.read_csv(full_path, **kwargs)

    if backend == "azure_blob":
        logger.info("Reading CSV (blob): %s", path)
        client = _get_blob_service_client()
        blob = client.get_blob_client(_get_container_name(), path)
        data = blob.download_blob().readall()
        return pd.read_csv(io.BytesIO(data), **kwargs)

    raise ValueError(f"Unknown STORAGE_BACKEND: {backend}")


def save_model(pipeline, path: str, config_dir: str = "") -> str:
    """Save a sklearn Pipeline to local filesystem or Azure Blob Storage."""
    backend = get_backend()

    if backend == "local":
        full_path = _resolve_local(path, config_dir)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        joblib.dump(pipeline, full_path)
        logger.info("Model saved (local): %s", full_path)
        return full_path

    if backend == "azure_blob":
        buf = io.BytesIO()
        joblib.dump(pipeline, buf)
        buf.seek(0)
        blob_path = _resolve_blob_path(path)
        client = _get_blob_service_client()
        blob = client.get_blob_client(_get_container_name(), blob_path)
        blob.upload_blob(buf, overwrite=True)
        logger.info("Model saved (blob): %s", blob_path)
        return blob_path

    raise ValueError(f"Unknown STORAGE_BACKEND: {backend}")


def load_model(path: str, config_dir: str = ""):
    """Load a sklearn Pipeline from local filesystem or Azure Blob Storage."""
    backend = get_backend()

    if backend == "local":
        full_path = _resolve_local(path, config_dir)
        if not os.path.exists(full_path):
            raise FileNotFoundError(
                f"Model artifact not found at '{full_path}'. "
                "Run 'python main.py train' first."
            )
        pipeline = joblib.load(full_path)
        logger.info("Model loaded (local): %s", full_path)
        return pipeline

    if backend == "azure_blob":
        blob_path = _resolve_blob_path(path)
        logger.info("Loading model (blob): %s", blob_path)
        client = _get_blob_service_client()
        blob = client.get_blob_client(_get_container_name(), blob_path)
        data = blob.download_blob().readall()
        pipeline = joblib.load(io.BytesIO(data))
        logger.info("Model loaded (blob): %s", blob_path)
        return pipeline

    raise ValueError(f"Unknown STORAGE_BACKEND: {backend}")


def save_json(data: dict, path: str, config_dir: str = "") -> str:
    """Save a dict as JSON to local filesystem or Azure Blob Storage."""
    backend = get_backend()

    if backend == "local":
        full_path = _resolve_local(path, config_dir)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("JSON saved (local): %s", full_path)
        return full_path

    if backend == "azure_blob":
        content = json.dumps(data, indent=2)
        client = _get_blob_service_client()
        blob = client.get_blob_client(_get_container_name(), path)
        blob.upload_blob(content, overwrite=True)
        logger.info("JSON saved (blob): %s", path)
        return path

    raise ValueError(f"Unknown STORAGE_BACKEND: {backend}")


def load_json(path: str, config_dir: str = "") -> dict:
    """Load a JSON file from local filesystem or Azure Blob Storage."""
    backend = get_backend()

    if backend == "local":
        full_path = _resolve_local(path, config_dir)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"JSON file not found: {full_path}")
        with open(full_path, "r") as f:
            return json.load(f)

    if backend == "azure_blob":
        logger.info("Loading JSON (blob): %s", path)
        client = _get_blob_service_client()
        blob = client.get_blob_client(_get_container_name(), path)
        data = blob.download_blob().readall()
        return json.loads(data)

    raise ValueError(f"Unknown STORAGE_BACKEND: {backend}")
