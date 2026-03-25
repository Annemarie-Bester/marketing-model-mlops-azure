# Operationalisation Guide

Steps to provision Azure infrastructure, configure Azure DevOps, and deploy the Bank Marketing prediction service to production. All commands run from the Dev Container (Azure CLI, kubectl, and Docker are pre-installed).

> **Prerequisite**: The codebase is complete — `Dockerfile.train`, `Dockerfile.infer`, K8s manifests, pipeline definitions (`.azure/`), and all source modules are committed. This guide covers infrastructure and platform configuration only.

---

## Table of Contents

1. [Azure Account & Resource Group](#1-azure-account--resource-group)
2. [Azure Container Registry (ACR)](#2-azure-container-registry-acr)
3. [Azure Kubernetes Service (AKS)](#3-azure-kubernetes-service-aks)
4. [ACR–AKS Integration Verification](#4-acr-aks-integration-verification)
5. [Azure Blob Storage](#5-azure-blob-storage)
6. [Azure Monitor & Application Insights](#6-azure-monitor--application-insights)
7. [Kubernetes Secrets](#7-kubernetes-secrets)
8. [Azure DevOps — Organisation & Project](#8-azure-devops--organisation--project)
9. [Azure DevOps — Service Connections](#9-azure-devops--service-connections)
10. [Azure DevOps — Pipeline Registration](#10-azure-devops--pipeline-registration)
11. [Azure DevOps — Pipeline Variables](#11-azure-devops--pipeline-variables)
12. [Azure DevOps — Environments & Approval Gates](#12-azure-devops--environments--approval-gates)
13. [GitHub — Branch Setup & Protection](#13-github--branch-setup--protection)
14. [Agent Pool Verification](#14-agent-pool-verification)
15. [ACR Image Retention](#15-acr-image-retention)
16. [Validation Sequence](#16-validation-sequence)

---

## 1. Azure Account & Resource Group

```bash
az login
az account set --subscription <subscription-id>
az account show
```

```bash
az group create \
  --name rg-bank-marketing \
  --location southafricanorth
```

---

## 2. Azure Container Registry (ACR)

```bash
az acr create \
  --resource-group rg-bank-marketing \
  --name bankmarketingacr \
  --sku Basic
```

Verify login:

```bash
az acr login --name bankmarketingacr
```

Test push (optional — confirms Docker ↔ ACR connectivity):

```bash
docker build -f Dockerfile.infer -t bank-marketing-api:local .
docker tag bank-marketing-api:local bankmarketingacr.azurecr.io/bank-marketing-api:test
docker push bankmarketingacr.azurecr.io/bank-marketing-api:test

# Verify
az acr repository list --name bankmarketingacr

# Clean up test image
az acr repository delete --name bankmarketingacr --image bank-marketing-api:test --yes
```

---

## 3. Azure Kubernetes Service (AKS)

```bash
az aks create \
  --resource-group rg-bank-marketing \
  --name bank-marketing-aks \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys \
  --attach-acr bankmarketingacr
```

> `--attach-acr` grants AKS the `AcrPull` role on the ACR — no separate `imagePullSecrets` needed when using the managed identity.

```bash
az aks get-credentials --resource-group rg-bank-marketing --name bank-marketing-aks
kubectl get nodes
```

Create namespaces:

```bash
kubectl create namespace bank-marketing
kubectl create namespace bank-marketing-dev
```

---

## 4. ACR–AKS Integration Verification

Confirm AKS can pull images from ACR before proceeding:

```bash
kubectl run acr-test \
  --image=bankmarketingacr.azurecr.io/bank-marketing-api:test \
  -n bank-marketing \
  --command -- sleep 3600
```

```bash
kubectl get pod acr-test -n bank-marketing
# Status should be Running (image pull succeeded)

# Clean up
kubectl delete pod acr-test -n bank-marketing
```

---

## 5. Azure Blob Storage

Azure Blob Storage serves two purposes:
- **Training data**: durable, remotely-accessible storage for the retraining pipeline
- **Model registry**: prefix-based model versioning (`builds/<buildId>/` → `staging/artifacts/` → `production/artifacts/`)

### Create Storage Account & Containers

```bash
az storage account create \
  --name bankmarketingdata \
  --resource-group rg-bank-marketing \
  --location southafricanorth \
  --sku Standard_LRS \
  --kind StorageV2
```

```bash
# Training data container
az storage container create \
  --name training-data \
  --account-name bankmarketingdata

# Model registry container (model.pkl, metrics.json, baseline)
az storage container create \
  --name model-registry \
  --account-name bankmarketingdata
```

### Upload Initial Training Data

Upload with a date-prefixed path to enable data versioning, then copy to `latest/` as the default retrain target:

```bash
az storage blob upload \
  --account-name bankmarketingdata \
  --container-name training-data \
  --name "$(date +%Y-%m-%d)/bank_marketing_data.csv" \
  --file data/raw/bank_marketing_data.csv \
  --auth-mode login

az storage blob copy start \
  --account-name bankmarketingdata \
  --source-container training-data \
  --source-blob "$(date +%Y-%m-%d)/bank_marketing_data.csv" \
  --destination-container training-data \
  --destination-blob latest/bank_marketing_data.csv
```

> When uploading new training data: always upload to a date-prefixed path first, then update `latest/`. This preserves the audit trail of which data each model version was trained on.

### Grant IAM Roles to the ADO Service Principal

The ADO service principal needs:
- Read access to training data
- Read+write access to the model registry
- Cluster User access to AKS for `kubectl apply` during deployments

```bash
# Get the service principal object ID from the ADO service connection
SP_ID=$(az ad sp show --id <client-id-from-ado-service-connection> --query id -o tsv)

# Read access for training data downloads
az role assignment create \
  --assignee $SP_ID \
  --role "Storage Blob Data Reader" \
  --scope "/subscriptions/<sub-id>/resourceGroups/rg-bank-marketing/providers/Microsoft.Storage/storageAccounts/bankmarketingdata/blobServices/default/containers/training-data"

# Read+write for model-registry (model promotion + baseline metrics)
az role assignment create \
  --assignee $SP_ID \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/<sub-id>/resourceGroups/rg-bank-marketing/providers/Microsoft.Storage/storageAccounts/bankmarketingdata/blobServices/default/containers/model-registry"

# AKS Cluster User — deploy manifests via kubectl in pipeline stages
az role assignment create \
  --assignee $SP_ID \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope "$(az aks show --resource-group rg-bank-marketing --name bank-marketing-aks --query id -o tsv)"
```

Verify:

```bash
az storage blob list --account-name bankmarketingdata --container-name training-data --auth-mode login
```

### Grant Developer Access (Optional)

Grant team members read-only access to Azure resources for debugging and local testing. Replace `<DEVELOPER_ID>` with each developer's Azure AD object ID.

```bash
# Resource Group: Reader (view resources in portal)
az role assignment create \
  --assignee <DEVELOPER_ID> \
  --role Reader \
  --resource-group rg-bank-marketing

# ACR: AcrPull (pull images for local testing)
az role assignment create \
  --assignee <DEVELOPER_ID> \
  --role AcrPull \
  --scope "$(az acr show --name bankmarketingacr --query id -o tsv)"

# AKS: Cluster User (debug via kubectl)
az role assignment create \
  --assignee <DEVELOPER_ID> \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope "$(az aks show --resource-group rg-bank-marketing --name bank-marketing-aks --query id -o tsv)"
```

---

## 6. Azure Monitor & Application Insights

Optional for initial deployment, recommended for production readiness.

```bash
az aks enable-addons \
  --resource-group rg-bank-marketing \
  --name bank-marketing-aks \
  --addons monitoring
```

```bash
az monitor app-insights component create \
  --app bank-marketing-insights \
  --location southafricanorth \
  --resource-group rg-bank-marketing
```

Note the instrumentation key for future integration with the FastAPI app.

---

## 7. Kubernetes Secrets

Create secrets in both namespaces. The K8s manifests reference these via `secretKeyRef`.

### API Key

```bash
kubectl create secret generic bank-marketing-api-key \
  --from-literal=API_KEY=<your-secure-api-key> \
  -n bank-marketing

kubectl create secret generic bank-marketing-api-key \
  --from-literal=API_KEY=<your-secure-api-key> \
  -n bank-marketing-dev
```

### Azure Storage Credentials

```bash
kubectl create secret generic azure-storage \
  --from-literal=ACCOUNT_NAME=bankmarketingdata \
  --from-literal=CONTAINER_NAME=model-registry \
  -n bank-marketing

kubectl create secret generic azure-storage \
  --from-literal=ACCOUNT_NAME=bankmarketingdata \
  --from-literal=CONTAINER_NAME=model-registry \
  -n bank-marketing-dev
```

> In CI/CD, the pipeline injects these values via the ADO variable group. For manual deployments, create the secrets as shown above.

---

## 8. Azure DevOps — Organisation & Project

### Create Organisation (if needed)

1. Go to [dev.azure.com](https://dev.azure.com) and sign in
2. Click **New organization** → choose a name → select region → **Create**

### Create Project

1. Click **New project**
   - Name: `bank-marketing-mlops`
   - Visibility: **Private**
   - Version control: **Git**
2. Confirm the project dashboard loads

### Connect to GitHub Repository

1. Project Settings → Service connections → **New service connection**
2. Select **GitHub** → authenticate via **OAuth** (recommended) or PAT with `repo` scope
3. Service connection name: `github-connection`
4. Check **Grant access permission to all pipelines**

> (Optional) Disable the unused default Azure Repos Git repo: Project Settings → Repos → Repositories → Disable

---

## 9. Azure DevOps — Service Connections

All created under: **Project Settings → Service connections → New service connection**

### Azure Resource Manager

| Setting | Value |
|---|---|
| Type | Azure Resource Manager |
| Authentication | Service principal (automatic) |
| Scope | Subscription or Resource Group (`rg-bank-marketing`) |
| Name | `azure-sub-connection` |
| Grant access | All pipelines |

### Docker Registry (ACR)

| Setting | Value |
|---|---|
| Type | Docker Registry |
| Registry type | Azure Container Registry |
| Registry | `bankmarketingacr` |
| Name | `acr-connection` |
| Grant access | All pipelines |

### Verify

All three connections should appear in Project Settings → Service connections:

| Connection | Type |
|---|---|
| `github-connection` | GitHub |
| `azure-sub-connection` | Azure Resource Manager |
| `acr-connection` | Docker Registry / ACR |

Optional — validate with a one-off test pipeline:

```yaml
# test-connections.yml (temporary — delete after verification)
trigger: none
pool:
  vmImage: ubuntu-latest
steps:
  - task: AzureCLI@2
    inputs:
      azureSubscription: 'azure-sub-connection'
      scriptType: bash
      scriptLocation: inlineScript
      inlineScript: |
        az acr repository list --name bankmarketingacr
        az aks show --resource-group rg-bank-marketing --name bank-marketing-aks --query name
```

---

## 10. Azure DevOps — Pipeline Registration

Register all three pipeline YAML files. The files must exist in the GitHub repo before registering.

> Pipeline files live under `.azure/` in the repository root. ADO does not auto-discover pipeline files — each is registered by pointing to its explicit path.

### Pipeline 1: PR Validation

1. Pipelines → **New pipeline** → **GitHub** → select repository
2. Select: **Existing Azure Pipelines YAML file**
3. Branch: `dev` → Path: `/.azure/pr-validation.yml`
4. Click **Run** to validate (or **Save** without running)
5. Rename to `pr-validation`

> ADO automatically installs a GitHub webhook to trigger the pipeline on PR events.

### Pipeline 2: CI/CD

1. Pipelines → **New pipeline** → **GitHub** → select repository
2. Select: **Existing Azure Pipelines YAML file**
3. Branch: `dev` → Path: `/.azure/azure-pipelines.yml`
4. Click **Save** (do not run — `main` branch triggers production deploy)
5. Rename to `ci-cd`

### Pipeline 3: Retrain

1. Pipelines → **New pipeline** → **GitHub** → select repository
2. Select: **Existing Azure Pipelines YAML file**
3. Branch: `main` → Path: `/.azure/retrain.yml`
4. Click **Save** (triggered manually, on schedule, or via API)
5. Rename to `retrain`

---

## 11. Azure DevOps — Pipeline Variables

Create a shared variable group: Pipelines → Library → **+ Variable group**

| Variable | Value | Secret? | Used by |
|---|---|---|---|
| `ACR_SERVICE_CONNECTION` | `acr-connection` | No | All pipelines |
| `ACR_NAME` | `bankmarketingacr` | No | All pipelines |
| `AKS_CLUSTER` | `bank-marketing-aks` | No | `azure-pipelines.yml`, `retrain.yml` |
| `RESOURCE_GROUP` | `rg-bank-marketing` | No | `azure-pipelines.yml`, `retrain.yml` |
| `AZURE_SUBSCRIPTION` | `azure-sub-connection` | No | `azure-pipelines.yml`, `retrain.yml` |
| `TRAIN_IMAGE_NAME` | `bank-marketing-train` | No | `azure-pipelines.yml`, `retrain.yml` |
| `INFER_IMAGE_NAME` | `bank-marketing-api` | No | `azure-pipelines.yml`, `retrain.yml` |
| `BLOB_STORAGE_ACCOUNT` | `bankmarketingdata` | No | `azure-pipelines.yml`, `retrain.yml` |
| `BLOB_CONTAINER_TRAINING` | `training-data` | No | `retrain.yml` |

- Variable group name: `bank-marketing-vars`
- Pipeline permissions: grant access to `pr-validation`, `ci-cd`, and `retrain` pipelines

---

## 12. Azure DevOps — Environments & Approval Gates

### Staging Environment

1. Pipelines → Environments → **New environment**
   - Name: `staging`
   - Resource: None
2. No approval gate needed — `CD_Dev` deploys automatically

### Production Environment

1. Pipelines → Environments → **New environment**
   - Name: `production`
   - Resource: None
2. Add **approval check**:
   - Environments → `production` → "..." → **Approvals and checks** → **Approvals**
   - Add approver(s)
   - Approval policy: **Any one approver**
   - Timeout: 72 hours
3. (Optional) Add **exclusive lock** check to prevent concurrent deployments

---

## 13. GitHub — Branch Setup & Protection

### Branch Setup

```bash
# Ensure dev branch exists
git checkout -b dev main    # skip if dev already exists
git push origin dev
```

Confirm `main` is the default branch: GitHub → Settings → General → Default branch → `main`

### Branch Protection — `dev`

Configure at: repository → Settings → Branches → Branch protection rules → **Add rule**

| Setting | Value |
|---|---|
| Branch name pattern | `dev` |
| Require PR before merging | Enabled (1 approval recommended) |
| Dismiss stale approvals on new commits | Enabled |
| Require status checks to pass | Enabled — add `pr-validation` |
| Require branches up to date before merging | Enabled |
| Require conversation resolution | Enabled |
| Do not allow bypassing | Enabled |

### Branch Protection — `main`

| Setting | Value |
|---|---|
| Branch name pattern | `main` |
| Require PR before merging | Enabled (1 approval) |
| Dismiss stale approvals on new commits | Enabled |
| Require status checks to pass | Enabled — add `pr-validation` |
| Require branches up to date before merging | Enabled |
| Require conversation resolution | Enabled |
| Do not allow bypassing | Enabled |

> GitHub configures allowed merge types at the **repository level** (Settings → General → Pull Requests), not per branch. Enable both squash merging and merge commits, then follow team convention per [git-workflow.md](git-workflow.md#merge-strategy).

---

## 14. Agent Pool Verification

The pipelines use `vmImage: ubuntu-latest` (Microsoft-hosted agents).

1. Organization Settings → Pipelines → Agent pools → **Azure Pipelines**
2. Confirm `ubuntu-latest` is available
3. Free-tier private projects: 1 parallel job, 1,800 minutes/month
   - Request more at [aka.ms/azpipelines-parallelism-request](https://aka.ms/azpipelines-parallelism-request) if needed

---

## 15. ACR Image Retention

Prevent the ACR Basic SKU (10 GiB) from filling with old training images:

```bash
az acr task create \
  --registry bankmarketingacr \
  --name purge-untagged \
  --cmd "acr purge --filter 'bank-marketing-train:train-[0-9]+' --ago 30d --untagged" \
  --schedule "0 1 * * *" \
  --context /dev/null
```

> Keeps `train-latest` and `latest` indefinitely. Purges build-ID-tagged images older than 30 days.

---

## 16. Validation Sequence

After all infrastructure and configuration is in place, validate end-to-end in this order:

### Step 1 — First PR → `dev`

1. Create a `feature/*` branch from `dev`
2. Open a PR targeting `dev`
3. Confirm `pr-validation` pipeline triggers automatically
4. Verify all stages pass: install → pytest → kubeconform → Docker build (train + infer) → smoke test

### Step 2 — First Merge → `dev`

1. Merge the PR into `dev`
2. Confirm `ci-cd` pipeline triggers
3. Verify CI stage passes, `TrainModel` runs, and `CD_Dev` deploys to `bank-marketing-dev`
4. Confirm pod is running:
   ```bash
   kubectl get pods -n bank-marketing-dev
   ```

### Step 3 — First PR → `main`

1. Create a `release/*` branch from `dev`
2. Open a PR targeting `main`
3. Confirm `pr-validation` triggers and passes

### Step 4 — First Merge → `main` (Production)

1. Merge the approved PR into `main`
2. Confirm `ci-cd` pipeline triggers, CI passes, and `CD_Main` deploys to `bank-marketing`
3. Approve the `production` environment gate when prompted
4. Verify production deployment:
   ```bash
   kubectl get pods -n bank-marketing
   kubectl get svc bank-marketing-api -n bank-marketing
   ```
5. Test the live endpoint:
   ```bash
   API_IP=$(kubectl get svc bank-marketing-api -n bank-marketing \
     -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

   curl -s http://$API_IP/health

   curl -s -X POST http://$API_IP/predict \
     -H "Content-Type: application/json" \
     -H "X-API-Key: <your-api-key>" \
     -d '{"age":35,"job":"management","marital":"married","education":"tertiary","default":"no","balance":1500.0,"housing":"yes","loan":"no","contact":"cellular","day":15,"month":"may","duration":250.0,"campaign":1,"pdays":-1,"previous":0,"poutcome":"unknown"}'
   ```

---

## Resource Summary

| Resource | Name | SKU / Size |
|---|---|---|
| Resource Group | `rg-bank-marketing` | — |
| Container Registry | `bankmarketingacr` | Basic |
| Kubernetes Cluster | `bank-marketing-aks` | 2× Standard_B2s |
| Storage Account | `bankmarketingdata` | Standard_LRS, StorageV2 |
| Application Insights | `bank-marketing-insights` | — |
| K8s Namespaces | `bank-marketing`, `bank-marketing-dev` | — |
| ADO Variable Group | `bank-marketing-vars` | — |
| ADO Environments | `staging`, `production` | — |
| Service Connections | `github-connection`, `azure-sub-connection`, `acr-connection` | — |
| Pipelines | `pr-validation`, `ci-cd`, `retrain` | — |
