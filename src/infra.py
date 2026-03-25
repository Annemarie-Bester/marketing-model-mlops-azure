"""
infra.py — Thin wrapper around Azure CLI commands for infrastructure provisioning.

Each function calls a single `az` CLI command via subprocess and returns
the CompletedProcess result. This design makes every Azure operation
independently testable via unittest.mock.patch('subprocess.run').

Set DRY_RUN = True (or env INFRA_DRY_RUN=1) to return realistic fake
responses without calling any external commands. Useful for:
  - Local notebook testing without Azure credentials
  - Validating the notebook flow end-to-end
  - Demonstrating the provisioning sequence

Used by: notebooks/07_operationalisation.ipynb
Tested by: tests/test_infra.py
"""

import json
import os
import subprocess
from typing import Optional

# ── Dry-run mode ─────────────────────────────────────────────────────────

DRY_RUN: bool = os.environ.get("INFRA_DRY_RUN", "0") == "1"


def _dry_result(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """Return a fake CompletedProcess for dry-run mode."""
    return subprocess.CompletedProcess(
        args=["dry-run"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


def run_az(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run an Azure CLI command and return the result.

    Args:
        args: Command arguments (e.g. ["group", "create", "--name", "rg"]).
        check: Raise CalledProcessError on non-zero exit code.

    Returns:
        subprocess.CompletedProcess with stdout/stderr captured.
    """
    if DRY_RUN:
        return _dry_result(stdout=_dry_run_response(args))
    cmd = ["az"] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def login_check() -> dict:
    """Verify the current Azure CLI login. Returns account info dict."""
    if DRY_RUN:
        return {
            "id": "00000000-0000-0000-0000-000000000000",
            "name": "dry-run-subscription",
            "user": {"name": "dry-run@local", "type": "user"},
        }
    result = run_az(["account", "show", "-o", "json"])
    return json.loads(result.stdout)


def set_subscription(subscription_id: str) -> subprocess.CompletedProcess:
    """Set the active Azure subscription."""
    return run_az(["account", "set", "--subscription", subscription_id])


def create_resource_group(name: str, location: str) -> subprocess.CompletedProcess:
    """Create a resource group."""
    return run_az(
        [
            "group",
            "create",
            "--name",
            name,
            "--location",
            location,
            "-o",
            "json",
        ]
    )


def create_acr(
    resource_group: str, name: str, sku: str = "Basic"
) -> subprocess.CompletedProcess:
    """Create an Azure Container Registry."""
    return run_az(
        [
            "acr",
            "create",
            "--resource-group",
            resource_group,
            "--name",
            name,
            "--sku",
            sku,
            "-o",
            "json",
        ]
    )


def create_aks(
    resource_group: str,
    name: str,
    node_count: int = 2,
    node_vm_size: str = "Standard_B2s",
    acr_name: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Create an AKS cluster, optionally attached to an ACR."""
    args = [
        "aks",
        "create",
        "--resource-group",
        resource_group,
        "--name",
        name,
        "--node-count",
        str(node_count),
        "--node-vm-size",
        node_vm_size,
        "--generate-ssh-keys",
        "-o",
        "json",
    ]
    if acr_name:
        args.extend(["--attach-acr", acr_name])
    return run_az(args)


def get_aks_credentials(resource_group: str, name: str) -> subprocess.CompletedProcess:
    """Download AKS cluster credentials into kubeconfig."""
    return run_az(
        [
            "aks",
            "get-credentials",
            "--resource-group",
            resource_group,
            "--name",
            name,
            "--overwrite-existing",
        ]
    )


def create_storage_account(
    name: str,
    resource_group: str,
    location: str,
    sku: str = "Standard_LRS",
) -> subprocess.CompletedProcess:
    """Create an Azure Storage account."""
    return run_az(
        [
            "storage",
            "account",
            "create",
            "--name",
            name,
            "--resource-group",
            resource_group,
            "--location",
            location,
            "--sku",
            sku,
            "--kind",
            "StorageV2",
            "-o",
            "json",
        ]
    )


def create_blob_container(
    account_name: str,
    container_name: str,
) -> subprocess.CompletedProcess:
    """Create a blob container in a storage account."""
    return run_az(
        [
            "storage",
            "container",
            "create",
            "--name",
            container_name,
            "--account-name",
            account_name,
            "--auth-mode",
            "login",
            "-o",
            "json",
        ]
    )


def upload_blob(
    account_name: str,
    container_name: str,
    blob_name: str,
    file_path: str,
) -> subprocess.CompletedProcess:
    """Upload a file to blob storage."""
    return run_az(
        [
            "storage",
            "blob",
            "upload",
            "--account-name",
            account_name,
            "--container-name",
            container_name,
            "--name",
            blob_name,
            "--file",
            file_path,
            "--auth-mode",
            "login",
            "--overwrite",
            "-o",
            "json",
        ]
    )


def copy_blob(
    account_name: str,
    source_container: str,
    source_blob: str,
    dest_container: str,
    dest_blob: str,
) -> subprocess.CompletedProcess:
    """Copy a blob within the same storage account."""
    return run_az(
        [
            "storage",
            "blob",
            "copy",
            "start",
            "--account-name",
            account_name,
            "--source-container",
            source_container,
            "--source-blob",
            source_blob,
            "--destination-container",
            dest_container,
            "--destination-blob",
            dest_blob,
        ]
    )


def enable_aks_monitoring(
    resource_group: str,
    name: str,
) -> subprocess.CompletedProcess:
    """Enable the AKS monitoring addon."""
    return run_az(
        [
            "aks",
            "enable-addons",
            "--resource-group",
            resource_group,
            "--name",
            name,
            "--addons",
            "monitoring",
            "-o",
            "json",
        ]
    )


def create_app_insights(
    app_name: str,
    resource_group: str,
    location: str,
) -> subprocess.CompletedProcess:
    """Create an Application Insights component."""
    return run_az(
        [
            "monitor",
            "app-insights",
            "component",
            "create",
            "--app",
            app_name,
            "--location",
            location,
            "--resource-group",
            resource_group,
            "-o",
            "json",
        ]
    )


def create_service_principal(
    name: str,
    role: str = "Contributor",
    scope: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Create a service principal for deployment automation.

    Args:
        name: Display name for the SP.
        role: RBAC role (default: Contributor).
        scope: Scope for the role assignment (e.g. resource group ID).

    Returns:
        CompletedProcess whose stdout contains JSON with appId, password, tenant.
    """
    args = [
        "ad",
        "sp",
        "create-for-rbac",
        "--name",
        name,
        "--role",
        role,
    ]
    if scope:
        args.extend(["--scopes", scope])
    args.extend(["-o", "json"])
    return run_az(args)


def assign_role(
    assignee: str,
    role: str,
    scope: str,
) -> subprocess.CompletedProcess:
    """Assign an RBAC role to a principal."""
    return run_az(
        [
            "role",
            "assignment",
            "create",
            "--assignee",
            assignee,
            "--role",
            role,
            "--scope",
            scope,
            "-o",
            "json",
        ]
    )


def run_kubectl(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a kubectl command and return the result."""
    if DRY_RUN:
        return _dry_result()
    cmd = ["kubectl"] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def create_k8s_namespace(name: str) -> subprocess.CompletedProcess:
    """Create a Kubernetes namespace."""
    return run_kubectl(["create", "namespace", name], check=False)


def create_k8s_secret(
    secret_name: str,
    namespace: str,
    literals: dict[str, str],
) -> subprocess.CompletedProcess:
    """Create a Kubernetes secret from literal key=value pairs."""
    args = ["create", "secret", "generic", secret_name, "-n", namespace]
    for key, value in literals.items():
        args.append(f"--from-literal={key}={value}")
    return run_kubectl(args, check=False)


def create_acr_purge_task(
    registry: str,
    task_name: str = "purge-untagged",
    filter_pattern: str = "bank-marketing-train:train-[0-9]+",
    ago: str = "30d",
) -> subprocess.CompletedProcess:
    """Create an ACR purge task for image retention."""
    return run_az(
        [
            "acr",
            "task",
            "create",
            "--registry",
            registry,
            "--name",
            task_name,
            "--cmd",
            f"acr purge --filter '{filter_pattern}' --ago {ago} --untagged",
            "--schedule",
            "0 1 * * *",
            "--context",
            "/dev/null",
        ]
    )


# ── Dry-run response generator ──────────────────────────────────────────


def _dry_run_response(args: list[str]) -> str:
    """Return realistic JSON stdout for az commands during dry-run.

    Inspects the command args to produce a plausible response so that
    downstream json.loads() calls in the notebook succeed.
    """
    cmd = " ".join(args[:4])  # first few tokens to identify the command

    # Extract --name / --resource-group values from args for realistic output
    def _arg(flag: str) -> str:
        try:
            return args[args.index(flag) + 1]
        except (ValueError, IndexError):
            return "dry-run-value"

    if "group create" in cmd:
        name = _arg("--name")
        loc = _arg("--location")
        return json.dumps(
            {
                "id": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/{name}",
                "name": name,
                "location": loc,
            }
        )

    if "ad sp create-for-rbac" in cmd:
        return json.dumps(
            {
                "appId": "dry-run-app-id-00000000",
                "password": "dry-run-password-DO-NOT-USE",
                "tenant": "dry-run-tenant-00000000",
            }
        )

    if "acr create" in cmd:
        name = _arg("--name")
        return json.dumps(
            {
                "id": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.ContainerRegistry/registries/{name}",
                "loginServer": f"{name}.azurecr.io",
                "name": name,
            }
        )

    if "aks create" in cmd:
        name = _arg("--name")
        return json.dumps(
            {
                "name": name,
                "kubernetesVersion": "1.29.0",
                "nodeResourceGroup": f"MC_rg_{name}_region",
            }
        )

    if "storage account create" in cmd:
        name = _arg("--name")
        return json.dumps(
            {
                "id": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/{name}",
                "name": name,
            }
        )

    if "app-insights component create" in cmd:
        return json.dumps(
            {
                "instrumentationKey": "dry-run-instrumentation-key",
                "connectionString": "InstrumentationKey=dry-run-key;IngestionEndpoint=https://localhost",
            }
        )

    # Default: empty JSON object (safe for json.loads if needed)
    return json.dumps({})
