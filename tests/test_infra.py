"""
test_infra.py — Tests for src/infra.py using subprocess mocking.

Every Azure CLI and kubectl call is mocked via unittest.mock.patch
so tests run without any Azure credentials, subscriptions, or clusters.
Each test verifies:
  1. The correct CLI command is constructed
  2. Return values are parsed correctly
  3. Edge cases (already-exists, failures) are handled
"""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from src.infra import (
    create_acr,
    create_acr_purge_task,
    create_aks,
    create_app_insights,
    create_blob_container,
    create_k8s_namespace,
    create_k8s_secret,
    create_resource_group,
    create_service_principal,
    create_storage_account,
    assign_role,
    copy_blob,
    enable_aks_monitoring,
    get_aks_credentials,
    login_check,
    run_az,
    run_kubectl,
    set_subscription,
    upload_blob,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _mock_result(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["az"], returncode=returncode, stdout=stdout, stderr=stderr,
    )


def _json_result(data: dict) -> subprocess.CompletedProcess:
    """Build a mock CompletedProcess with JSON stdout."""
    return _mock_result(stdout=json.dumps(data))


# ── run_az / run_kubectl ─────────────────────────────────────────────────


class TestRunAz:
    @patch("src.infra.subprocess.run")
    def test_prepends_az(self, mock_run):
        mock_run.return_value = _mock_result()
        run_az(["account", "show"])
        mock_run.assert_called_once_with(
            ["az", "account", "show"],
            capture_output=True, text=True, check=True,
        )

    @patch("src.infra.subprocess.run")
    def test_check_false(self, mock_run):
        mock_run.return_value = _mock_result(returncode=1)
        result = run_az(["fail"], check=False)
        assert result.returncode == 1
        mock_run.assert_called_once_with(
            ["az", "fail"],
            capture_output=True, text=True, check=False,
        )


class TestRunKubectl:
    @patch("src.infra.subprocess.run")
    def test_prepends_kubectl(self, mock_run):
        mock_run.return_value = _mock_result()
        run_kubectl(["get", "pods"])
        mock_run.assert_called_once_with(
            ["kubectl", "get", "pods"],
            capture_output=True, text=True, check=True,
        )


# ── Login & Subscription ────────────────────────────────────────────────


class TestLoginCheck:
    @patch("src.infra.run_az")
    def test_returns_account_dict(self, mock_az):
        mock_az.return_value = _json_result({
            "id": "sub-123",
            "name": "Test Sub",
            "user": {"name": "user@test.com", "type": "user"},
        })
        account = login_check()
        assert account["id"] == "sub-123"
        assert account["user"]["name"] == "user@test.com"
        mock_az.assert_called_once_with(["account", "show", "-o", "json"])


class TestSetSubscription:
    @patch("src.infra.run_az")
    def test_sets_subscription(self, mock_az):
        mock_az.return_value = _mock_result()
        set_subscription("sub-456")
        mock_az.assert_called_once_with(
            ["account", "set", "--subscription", "sub-456"]
        )


# ── Resource Group ───────────────────────────────────────────────────────


class TestCreateResourceGroup:
    @patch("src.infra.run_az")
    def test_creates_rg(self, mock_az):
        mock_az.return_value = _json_result({
            "id": "/subscriptions/sub/resourceGroups/rg-test",
            "name": "rg-test",
            "location": "eastus",
        })
        result = create_resource_group("rg-test", "eastus")
        info = json.loads(result.stdout)
        assert info["name"] == "rg-test"
        mock_az.assert_called_once_with([
            "group", "create",
            "--name", "rg-test",
            "--location", "eastus",
            "-o", "json",
        ])


# ── Service Principal ───────────────────────────────────────────────────


class TestCreateServicePrincipal:
    @patch("src.infra.run_az")
    def test_creates_sp_with_scope(self, mock_az):
        mock_az.return_value = _json_result({
            "appId": "app-123",
            "password": "secret-pwd",
            "tenant": "tenant-abc",
        })
        result = create_service_principal(
            "sp-test", role="Contributor", scope="/subscriptions/sub/resourceGroups/rg"
        )
        sp = json.loads(result.stdout)
        assert sp["appId"] == "app-123"
        assert sp["password"] == "secret-pwd"
        mock_az.assert_called_once_with([
            "ad", "sp", "create-for-rbac",
            "--name", "sp-test",
            "--role", "Contributor",
            "--scopes", "/subscriptions/sub/resourceGroups/rg",
            "-o", "json",
        ])

    @patch("src.infra.run_az")
    def test_creates_sp_without_scope(self, mock_az):
        mock_az.return_value = _json_result(
            {"appId": "a", "password": "p", "tenant": "t"})
        create_service_principal("sp-no-scope")
        args = mock_az.call_args[0][0]
        assert "--scopes" not in args


class TestAssignRole:
    @patch("src.infra.run_az")
    def test_assigns_role(self, mock_az):
        mock_az.return_value = _mock_result()
        assign_role("app-123", "AcrPush", "/subscriptions/sub/acr")
        mock_az.assert_called_once_with([
            "role", "assignment", "create",
            "--assignee", "app-123",
            "--role", "AcrPush",
            "--scope", "/subscriptions/sub/acr",
            "-o", "json",
        ])


# ── ACR ──────────────────────────────────────────────────────────────────


class TestCreateAcr:
    @patch("src.infra.run_az")
    def test_creates_acr(self, mock_az):
        mock_az.return_value = _json_result({
            "id": "/acr/test",
            "loginServer": "testacr.azurecr.io",
            "name": "testacr",
        })
        result = create_acr("rg-test", "testacr")
        info = json.loads(result.stdout)
        assert info["loginServer"] == "testacr.azurecr.io"
        mock_az.assert_called_once_with([
            "acr", "create",
            "--resource-group", "rg-test",
            "--name", "testacr",
            "--sku", "Basic",
            "-o", "json",
        ])


# ── AKS ──────────────────────────────────────────────────────────────────


class TestCreateAks:
    @patch("src.infra.run_az")
    def test_creates_aks_with_acr(self, mock_az):
        mock_az.return_value = _json_result({
            "name": "test-aks",
            "kubernetesVersion": "1.29.0",
            "nodeResourceGroup": "MC_rg_test",
        })
        result = create_aks("rg-test", "test-aks",
                            node_count=2, acr_name="testacr")
        info = json.loads(result.stdout)
        assert info["name"] == "test-aks"
        args = mock_az.call_args[0][0]
        assert "--attach-acr" in args
        assert "testacr" in args
        assert "--node-count" in args
        assert "2" in args

    @patch("src.infra.run_az")
    def test_creates_aks_without_acr(self, mock_az):
        mock_az.return_value = _json_result({"name": "test"})
        create_aks("rg-test", "test-aks")
        args = mock_az.call_args[0][0]
        assert "--attach-acr" not in args


class TestGetAksCredentials:
    @patch("src.infra.run_az")
    def test_downloads_credentials(self, mock_az):
        mock_az.return_value = _mock_result()
        get_aks_credentials("rg-test", "test-aks")
        mock_az.assert_called_once_with([
            "aks", "get-credentials",
            "--resource-group", "rg-test",
            "--name", "test-aks",
            "--overwrite-existing",
        ])


# ── Storage ──────────────────────────────────────────────────────────────


class TestCreateStorageAccount:
    @patch("src.infra.run_az")
    def test_creates_storage(self, mock_az):
        mock_az.return_value = _json_result({
            "id": "/sa/test",
            "name": "teststorage",
        })
        result = create_storage_account("teststorage", "rg-test", "eastus")
        info = json.loads(result.stdout)
        assert info["name"] == "teststorage"
        args = mock_az.call_args[0][0]
        assert "--kind" in args
        assert "StorageV2" in args


class TestCreateBlobContainer:
    @patch("src.infra.run_az")
    def test_creates_container(self, mock_az):
        mock_az.return_value = _mock_result()
        create_blob_container("teststorage", "training-data")
        mock_az.assert_called_once_with([
            "storage", "container", "create",
            "--name", "training-data",
            "--account-name", "teststorage",
            "--auth-mode", "login",
            "-o", "json",
        ])


class TestUploadBlob:
    @patch("src.infra.run_az")
    def test_uploads_blob(self, mock_az):
        mock_az.return_value = _mock_result()
        upload_blob("acc", "container", "path/file.csv", "/local/file.csv")
        args = mock_az.call_args[0][0]
        assert "blob" in args
        assert "upload" in args
        assert "--overwrite" in args
        assert "--auth-mode" in args


class TestCopyBlob:
    @patch("src.infra.run_az")
    def test_copies_blob(self, mock_az):
        mock_az.return_value = _mock_result()
        copy_blob("acc", "src-c", "src-b", "dst-c", "dst-b")
        args = mock_az.call_args[0][0]
        assert "--source-container" in args
        assert "--destination-blob" in args


# ── Monitoring ───────────────────────────────────────────────────────────


class TestEnableAksMonitoring:
    @patch("src.infra.run_az")
    def test_enables_monitoring(self, mock_az):
        mock_az.return_value = _mock_result()
        enable_aks_monitoring("rg-test", "test-aks")
        args = mock_az.call_args[0][0]
        assert "--addons" in args
        assert "monitoring" in args


class TestCreateAppInsights:
    @patch("src.infra.run_az")
    def test_creates_app_insights(self, mock_az):
        mock_az.return_value = _json_result({
            "instrumentationKey": "key-123",
            "connectionString": "InstrumentationKey=key-123;...",
        })
        result = create_app_insights("test-insights", "rg-test", "eastus")
        info = json.loads(result.stdout)
        assert info["instrumentationKey"] == "key-123"


# ── Kubernetes ───────────────────────────────────────────────────────────


class TestCreateK8sNamespace:
    @patch("src.infra.run_kubectl")
    def test_creates_namespace(self, mock_kubectl):
        mock_kubectl.return_value = _mock_result()
        result = create_k8s_namespace("bank-marketing")
        mock_kubectl.assert_called_once_with(
            ["create", "namespace", "bank-marketing"], check=False,
        )

    @patch("src.infra.run_kubectl")
    def test_already_exists(self, mock_kubectl):
        mock_kubectl.return_value = _mock_result(
            returncode=1,
            stderr='Error from server (AlreadyExists): namespaces "bank-marketing" already exists',
        )
        result = create_k8s_namespace("bank-marketing")
        assert result.returncode == 1
        assert "AlreadyExists" in result.stderr


class TestCreateK8sSecret:
    @patch("src.infra.run_kubectl")
    def test_creates_secret_with_literals(self, mock_kubectl):
        mock_kubectl.return_value = _mock_result()
        create_k8s_secret("api-key", "bank-marketing", {"API_KEY": "test123"})
        args = mock_kubectl.call_args[0][0]
        assert "create" in args
        assert "secret" in args
        assert "--from-literal=API_KEY=test123" in args
        assert "-n" in args
        assert "bank-marketing" in args

    @patch("src.infra.run_kubectl")
    def test_creates_secret_multiple_literals(self, mock_kubectl):
        mock_kubectl.return_value = _mock_result()
        create_k8s_secret("storage", "ns", {"A": "1", "B": "2"})
        args = mock_kubectl.call_args[0][0]
        assert "--from-literal=A=1" in args
        assert "--from-literal=B=2" in args

    @patch("src.infra.run_kubectl")
    def test_already_exists(self, mock_kubectl):
        mock_kubectl.return_value = _mock_result(
            returncode=1,
            stderr='Error from server (AlreadyExists): secrets "api-key" already exists',
        )
        result = create_k8s_secret("api-key", "ns", {"K": "V"})
        assert result.returncode == 1
        assert "AlreadyExists" in result.stderr


# ── ACR Purge Task ───────────────────────────────────────────────────────


class TestCreateAcrPurgeTask:
    @patch("src.infra.run_az")
    def test_creates_purge_task(self, mock_az):
        mock_az.return_value = _mock_result()
        create_acr_purge_task("testacr")
        args = mock_az.call_args[0][0]
        assert "acr" in args
        assert "task" in args
        assert "create" in args
        assert "--schedule" in args
        assert "--registry" in args
        assert "testacr" in args


# ── Integration: notebook flow simulation ────────────────────────────────


class TestNotebookFlowEndToEnd:
    """Simulates the full notebook execution order with all calls mocked.

    Verifies that the notebook's function call sequence is valid and that
    outputs from early steps (e.g. resource group ID, SP app ID) are used
    correctly in later steps.
    """

    @patch("src.infra.run_az")
    @patch("src.infra.run_kubectl")
    def test_full_provisioning_flow(self, mock_kubectl, mock_az):
        # Configure mock responses for each call in sequence
        rg_id = "/subscriptions/sub-123/resourceGroups/rg-bank-marketing"
        acr_id = f"{rg_id}/providers/Microsoft.ContainerRegistry/registries/testacr"
        sa_id = f"{rg_id}/providers/Microsoft.Storage/storageAccounts/teststorage"

        call_count = {"n": 0}
        responses = [
            # login_check
            _json_result({"id": "sub-123", "name": "Test",
                         "user": {"name": "u@t.com"}}),
            # set_subscription
            _mock_result(),
            # create_resource_group
            _json_result(
                {"id": rg_id, "name": "rg-bank-marketing", "location": "eastus"}),
            # create_service_principal
            _json_result(
                {"appId": "app-sp", "password": "pwd", "tenant": "t"}),
            # create_acr
            _json_result(
                {"id": acr_id, "loginServer": "testacr.azurecr.io", "name": "testacr"}),
            # assign_role (AcrPush)
            _mock_result(),
            # create_aks
            _json_result(
                {"name": "test-aks", "kubernetesVersion": "1.29.0", "nodeResourceGroup": "MC"}),
            # get_aks_credentials
            _mock_result(),
            # create_storage_account
            _json_result({"id": sa_id, "name": "teststorage"}),
            # create_blob_container (training-data)
            _mock_result(),
            # create_blob_container (model-registry)
            _mock_result(),
            # assign_role (Blob Data Reader)
            _mock_result(),
            # assign_role (Blob Data Contributor)
            _mock_result(),
            # enable_aks_monitoring
            _mock_result(),
            # create_app_insights
            _json_result({"instrumentationKey": "k",
                         "connectionString": "cs"}),
            # create_acr_purge_task
            _mock_result(),
        ]

        def az_side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        mock_az.side_effect = az_side_effect
        mock_kubectl.return_value = _mock_result()

        # ── Simulate notebook cell execution ──

        # Cell 1: Login
        account = login_check()
        assert account["id"] == "sub-123"
        set_subscription("sub-123")

        # Cell 2: Resource Group + Service Principal
        rg_result = create_resource_group("rg-bank-marketing", "eastus")
        rg_info = json.loads(rg_result.stdout)
        assert rg_info["id"] == rg_id

        sp_result = create_service_principal(
            "sp-test", role="Contributor", scope=rg_id)
        sp_info = json.loads(sp_result.stdout)
        sp_app_id = sp_info["appId"]
        assert sp_app_id == "app-sp"

        # Cell 3: ACR + role
        acr_result = create_acr("rg-bank-marketing", "testacr")
        acr_info = json.loads(acr_result.stdout)
        assign_role(sp_app_id, "AcrPush", acr_info["id"])

        # Cell 4: AKS
        aks_result = create_aks("rg-bank-marketing",
                                "test-aks", acr_name="testacr")
        get_aks_credentials("rg-bank-marketing", "test-aks")

        # Cell 5: K8s namespaces (kubectl)
        create_k8s_namespace("bank-marketing")
        create_k8s_namespace("bank-marketing-dev")

        # Cell 6: Storage
        sa_result = create_storage_account(
            "teststorage", "rg-bank-marketing", "eastus")
        sa_info = json.loads(sa_result.stdout)
        create_blob_container("teststorage", "training-data")
        create_blob_container("teststorage", "model-registry")

        training_scope = f"{sa_info['id']}/blobServices/default/containers/training-data"
        registry_scope = f"{sa_info['id']}/blobServices/default/containers/model-registry"
        assign_role(sp_app_id, "Storage Blob Data Reader", training_scope)
        assign_role(sp_app_id, "Storage Blob Data Contributor", registry_scope)

        # Cell 7: Monitoring
        enable_aks_monitoring("rg-bank-marketing", "test-aks")
        ai_result = create_app_insights(
            "test-insights", "rg-bank-marketing", "eastus")
        ai_info = json.loads(ai_result.stdout)
        assert ai_info["instrumentationKey"] == "k"

        # Cell 8: K8s secrets (kubectl)
        for ns in ["bank-marketing", "bank-marketing-dev"]:
            create_k8s_secret("bank-marketing-api-key",
                              ns, {"API_KEY": "test"})
            create_k8s_secret("azure-storage", ns, {
                "ACCOUNT_NAME": "teststorage",
                "CONTAINER_NAME": "model-registry",
            })

        # Cell 9: ACR purge
        create_acr_purge_task("testacr")

        # Verify all az calls were made
        assert call_count["n"] == len(responses), \
            f"Expected {len(responses)} az calls, got {call_count['n']}"

        # Verify kubectl calls: 2 namespaces + 4 secrets = 6
        assert mock_kubectl.call_count == 6


# ── Dry-run mode ─────────────────────────────────────────────────────────


class TestDryRunMode:
    """Tests that DRY_RUN=True returns fake responses without subprocess."""

    def _enable_dry_run(self, monkeypatch):
        """Enable dry-run mode on the infra module."""
        import src.infra
        monkeypatch.setattr(src.infra, "DRY_RUN", True)

    def test_run_az_returns_fake_result(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = run_az(["group", "create", "--name",
                        "rg", "--location", "eastus"])
        assert result.returncode == 0
        assert result.args == ["dry-run"]
        data = json.loads(result.stdout)
        assert data["name"] == "rg"

    def test_run_kubectl_returns_fake_result(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = run_kubectl(["create", "namespace", "test-ns"])
        assert result.returncode == 0
        assert result.args == ["dry-run"]

    def test_login_check_returns_dict(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        account = login_check()
        assert "id" in account
        assert account["user"]["name"] == "dry-run@local"

    @patch("src.infra.subprocess.run")
    def test_no_subprocess_called(self, mock_run, monkeypatch):
        """Dry-run must never call subprocess.run."""
        self._enable_dry_run(monkeypatch)
        run_az(["account", "show"])
        run_kubectl(["get", "pods"])
        login_check()
        mock_run.assert_not_called()

    def test_resource_group_response(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = create_resource_group("rg-test", "eastus")
        data = json.loads(result.stdout)
        assert data["name"] == "rg-test"
        assert "rg-test" in data["id"]

    def test_service_principal_response(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = create_service_principal("sp-test", scope="/sub/rg")
        data = json.loads(result.stdout)
        assert "appId" in data
        assert "password" in data
        assert "tenant" in data

    def test_acr_response(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = create_acr("rg", "myacr")
        data = json.loads(result.stdout)
        assert data["loginServer"] == "myacr.azurecr.io"
        assert data["name"] == "myacr"

    def test_aks_response(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = create_aks("rg", "my-aks", acr_name="myacr")
        data = json.loads(result.stdout)
        assert data["name"] == "my-aks"
        assert "kubernetesVersion" in data

    def test_storage_account_response(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = create_storage_account("mysa", "rg", "eastus")
        data = json.loads(result.stdout)
        assert data["name"] == "mysa"
        assert "mysa" in data["id"]

    def test_app_insights_response(self, monkeypatch):
        self._enable_dry_run(monkeypatch)
        result = create_app_insights("ai-test", "rg", "eastus")
        data = json.loads(result.stdout)
        assert "instrumentationKey" in data
        assert "connectionString" in data

    def test_full_notebook_flow_dry_run(self, monkeypatch):
        """Run the entire notebook flow in dry-run — no mocking needed."""
        self._enable_dry_run(monkeypatch)

        # Login
        account = login_check()
        assert account["id"]

        set_subscription("sub-123")

        # Resource Group + SP
        rg = json.loads(create_resource_group("rg-test", "eastus").stdout)
        sp = json.loads(
            create_service_principal("sp", scope=rg["id"]).stdout
        )
        sp_app_id = sp["appId"]

        # ACR
        acr = json.loads(create_acr("rg-test", "testacr").stdout)
        assign_role(sp_app_id, "AcrPush", acr["id"])

        # AKS
        aks = json.loads(
            create_aks("rg-test", "test-aks", acr_name="testacr").stdout
        )
        get_aks_credentials("rg-test", "test-aks")

        # K8s
        create_k8s_namespace("bank-marketing")
        create_k8s_namespace("bank-marketing-dev")

        # Storage
        sa = json.loads(
            create_storage_account("mysa", "rg-test", "eastus").stdout
        )
        create_blob_container("mysa", "training-data")
        create_blob_container("mysa", "model-registry")
        assign_role(sp_app_id, "Storage Blob Data Reader", sa["id"])
        assign_role(sp_app_id, "Storage Blob Data Contributor", sa["id"])

        # Monitoring
        enable_aks_monitoring("rg-test", "test-aks")
        ai = json.loads(
            create_app_insights("ai", "rg-test", "eastus").stdout
        )
        assert ai["instrumentationKey"]

        # Secrets
        for ns in ["bank-marketing", "bank-marketing-dev"]:
            create_k8s_secret("api-key", ns, {"API_KEY": "test"})
            create_k8s_secret("storage", ns, {"A": "1"})

        # ACR purge
        create_acr_purge_task("testacr")
