"""
test_storage.py — Unit tests for src/storage.py.

Strategy:
- Local backend: use tmp_path (pytest fixture) for real filesystem I/O.
- Azure Blob backend: mock _get_blob_service_client and _get_container_name
  so no live credentials are needed.
- Helper functions (_resolve_local, _resolve_blob_path, get_backend, etc.)
  tested directly without backend I/O.
"""

import io
import json
import os
from unittest.mock import MagicMock, patch

import joblib
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import src.storage as storage


# ── Helpers ──────────────────────────────────────────────────────────────────


def _tiny_pipeline():
    """Return a minimal fitted pipeline for serialisation tests.

    Uses StandardScaler (not a lambda) so joblib can pickle it.
    """
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(random_state=0, max_iter=200)),
    ])
    pipe.fit([[0], [1]], [0, 1])
    return pipe


def _mock_blob_client(data: bytes = b""):
    """Return a mock BlobServiceClient whose download returns `data`."""
    mock_blob = MagicMock()
    mock_blob.download_blob.return_value.readall.return_value = data
    mock_container = MagicMock()
    mock_service = MagicMock()
    mock_service.get_blob_client.return_value = mock_blob
    return mock_service, mock_blob


# ══════════════════════════════════════════════════════════════════════════════
# 1. Helper functions
# ══════════════════════════════════════════════════════════════════════════════


class TestGetBackend:
    def test_defaults_to_local(self, monkeypatch):
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        assert storage.get_backend() == "local"

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")
        assert storage.get_backend() == "azure_blob"


class TestResolveLocal:
    def test_relative_path_joins_config_dir(self):
        result = storage._resolve_local("artifacts/model.pkl", "/project")
        assert result == "/project/artifacts/model.pkl"

    def test_absolute_path_returned_unchanged(self):
        result = storage._resolve_local("/abs/path/model.pkl", "/project")
        assert result == "/abs/path/model.pkl"


class TestResolveBlobPath:
    def test_no_prefix_returns_path_unchanged(self, monkeypatch):
        monkeypatch.delenv("MODEL_BLOB_PREFIX", raising=False)
        assert storage._resolve_blob_path(
            "artifacts/model.pkl") == "artifacts/model.pkl"

    def test_prefix_prepended(self, monkeypatch):
        monkeypatch.setenv("MODEL_BLOB_PREFIX", "staging")
        assert storage._resolve_blob_path(
            "artifacts/model.pkl") == "staging/artifacts/model.pkl"

    def test_production_prefix(self, monkeypatch):
        monkeypatch.setenv("MODEL_BLOB_PREFIX", "production")
        assert storage._resolve_blob_path(
            "artifacts/model.pkl") == "production/artifacts/model.pkl"


class TestGetContainerName:
    def test_raises_when_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("AZURE_STORAGE_CONTAINER", raising=False)
        with pytest.raises(EnvironmentError, match="AZURE_STORAGE_CONTAINER"):
            storage._get_container_name()

    def test_returns_container_name(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "my-container")
        assert storage._get_container_name() == "my-container"


class TestGetBlobServiceClient:
    def test_raises_when_no_credentials(self, monkeypatch):
        monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_NAME", raising=False)
        with pytest.raises(EnvironmentError, match="AZURE_STORAGE_CONNECTION_STRING"):
            storage._get_blob_service_client()


# ══════════════════════════════════════════════════════════════════════════════
# 2. Local backend — save_model / load_model
# ══════════════════════════════════════════════════════════════════════════════


class TestSaveLoadModelLocal:
    def test_save_model_writes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        pipe = _tiny_pipeline()
        dest = str(tmp_path / "artifacts" / "model.pkl")
        result = storage.save_model(pipe, dest, config_dir="")
        assert os.path.exists(result)

    def test_load_model_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        pipe = _tiny_pipeline()
        dest = str(tmp_path / "artifacts" / "model.pkl")
        storage.save_model(pipe, dest, config_dir="")
        loaded = storage.load_model(dest, config_dir="")
        assert hasattr(loaded, "predict")

    def test_load_model_raises_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        with pytest.raises(FileNotFoundError, match="main.py train"):
            storage.load_model(str(tmp_path / "missing.pkl"), config_dir="")

    def test_save_model_unknown_backend_raises(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        with pytest.raises(ValueError, match="Unknown STORAGE_BACKEND"):
            storage.save_model(_tiny_pipeline(), "model.pkl")

    def test_load_model_unknown_backend_raises(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        with pytest.raises(ValueError, match="Unknown STORAGE_BACKEND"):
            storage.load_model("model.pkl")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Local backend — save_json / load_json
# ══════════════════════════════════════════════════════════════════════════════


class TestSaveLoadJsonLocal:
    def test_save_json_writes_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        dest = str(tmp_path / "artifacts" / "metrics.json")
        storage.save_json({"roc_auc": 0.9}, dest, config_dir="")
        with open(dest) as f:
            data = json.load(f)
        assert data["roc_auc"] == 0.9

    def test_load_json_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        dest = str(tmp_path / "artifacts" / "metrics.json")
        storage.save_json({"f1": 0.75}, dest, config_dir="")
        loaded = storage.load_json(dest, config_dir="")
        assert loaded["f1"] == 0.75

    def test_load_json_raises_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        with pytest.raises(FileNotFoundError):
            storage.load_json(str(tmp_path / "missing.json"), config_dir="")

    def test_save_json_unknown_backend_raises(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        with pytest.raises(ValueError, match="Unknown STORAGE_BACKEND"):
            storage.save_json({}, "metrics.json")

    def test_load_json_unknown_backend_raises(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        with pytest.raises(ValueError, match="Unknown STORAGE_BACKEND"):
            storage.load_json("metrics.json")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Local backend — read_csv
# ══════════════════════════════════════════════════════════════════════════════


class TestReadCsvLocal:
    def test_read_csv_returns_dataframe(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        csv_path = str(tmp_path / "data.csv")
        pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(csv_path, index=False)
        df = storage.read_csv(csv_path, config_dir="")
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2

    def test_read_csv_unknown_backend_raises(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        with pytest.raises(ValueError, match="Unknown STORAGE_BACKEND"):
            storage.read_csv("data.csv")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Azure Blob backend — all functions (mocked)
# ══════════════════════════════════════════════════════════════════════════════


class TestBlobBackend:
    def test_save_model_blob(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "ml-models")
        monkeypatch.delenv("MODEL_BLOB_PREFIX", raising=False)
        mock_service, mock_blob = _mock_blob_client()
        with patch("src.storage._get_blob_service_client", return_value=mock_service):
            result = storage.save_model(
                _tiny_pipeline(), "artifacts/model.pkl")
        mock_blob.upload_blob.assert_called_once()
        assert result == "artifacts/model.pkl"

    def test_save_model_blob_with_prefix(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "ml-models")
        monkeypatch.setenv("MODEL_BLOB_PREFIX", "staging")
        mock_service, mock_blob = _mock_blob_client()
        with patch("src.storage._get_blob_service_client", return_value=mock_service):
            result = storage.save_model(
                _tiny_pipeline(), "artifacts/model.pkl")
        assert result == "staging/artifacts/model.pkl"

    def test_load_model_blob(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "ml-models")
        monkeypatch.delenv("MODEL_BLOB_PREFIX", raising=False)
        # Serialise a real pipeline so joblib.load succeeds
        buf = io.BytesIO()
        joblib.dump(_tiny_pipeline(), buf)
        mock_service, mock_blob = _mock_blob_client(data=buf.getvalue())
        with patch("src.storage._get_blob_service_client", return_value=mock_service):
            loaded = storage.load_model("artifacts/model.pkl")
        assert hasattr(loaded, "predict")

    def test_save_json_blob(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "ml-models")
        mock_service, mock_blob = _mock_blob_client()
        with patch("src.storage._get_blob_service_client", return_value=mock_service):
            result = storage.save_json(
                {"roc_auc": 0.9}, "artifacts/metrics.json")
        mock_blob.upload_blob.assert_called_once()
        assert result == "artifacts/metrics.json"

    def test_load_json_blob(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "ml-models")
        payload = json.dumps({"roc_auc": 0.88}).encode()
        mock_service, mock_blob = _mock_blob_client(data=payload)
        with patch("src.storage._get_blob_service_client", return_value=mock_service):
            result = storage.load_json("artifacts/metrics.json")
        assert result["roc_auc"] == 0.88

    def test_read_csv_blob(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "ml-models")
        csv_bytes = b"a,b\n1,2\n3,4\n"
        mock_service, mock_blob = _mock_blob_client(data=csv_bytes)
        with patch("src.storage._get_blob_service_client", return_value=mock_service):
            df = storage.read_csv("data/raw/data.csv")
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2
