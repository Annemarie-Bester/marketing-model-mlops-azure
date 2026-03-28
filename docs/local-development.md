# Local Development Guide

Step-by-step instructions for running and testing every component of the project locally — from environment setup through containerised smoke tests.

> **Section order** mirrors the CI/CD pipeline stages documented in [ci-cd-pipeline.md](ci-cd-pipeline.md): install → test → validate manifests → Docker build → container smoke test → Kubernetes deploy.

---

## Interactive Notebooks

The fastest way to work through local development is to run the notebooks in `notebooks/`. Each notebook corresponds to a section below, executes the exact commands documented here, and lets you modify inputs cell-by-cell without leaving VS Code.

| Notebook | Covers | Sections below |
|---|---|---|
| [notebooks/01_devcontainer_setup.ipynb](../notebooks/01_devcontainer_setup.ipynb) | Dev Container verification, dependency install, project structure, config check, dataset | §1, §2, §3 |
| [notebooks/03_ml_pipeline.ipynb](../notebooks/03_ml_pipeline.ipynb) | Train, batch predict, pytest suite, direct inference | §4, §5, §11 |
| [notebooks/04_docker_testing.ipynb](../notebooks/04_docker_testing.ipynb) | Docker access, image build, container smoke tests, edge cases | §7, §8, §9 |
| [notebooks/05_kubernetes_setup.ipynb](../notebooks/05_kubernetes_setup.ipynb) | kubectl/kind install, cluster bootstrap, manifest validation, deploy to both namespaces, CD_Dev simulation | §6, §10 |
| [notebooks/06_cleanup.ipynb](../notebooks/06_cleanup.ipynb) | Remove all local resources (container, image, kind cluster, artifacts, binaries) | — |
| [notebooks/08_prediction_testing.ipynb](../notebooks/08_prediction_testing.ipynb) | FastAPI health checks, single-record predict, batch predict, edge cases, full API test suite, individual test groups | §8, §9 |

Run notebooks in order: `01` → `02` → `03` → `04` → `05`. Run `06` to tear everything down. Run `08` to exercise the prediction API interactively. The reference commands in the sections below remain the authoritative source; the notebooks simply provide an interactive execution layer on top.

---

## Prerequisites

| Tool | Purpose | Install |
|---|---|---|
| VS Code | Editor + Dev Container host | [code.visualstudio.com](https://code.visualstudio.com/) |
| Docker Desktop | Container runtime for Dev Container, builds, and Kubernetes | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Dev Containers extension | VS Code extension for containerised development | `ms-vscode-remote.remote-containers` |

All other tooling (Python 3.12, pip, Azure CLI, Docker CLI) is pre-installed inside the Dev Container.

---

## 1. Start the Dev Container

> **Notebook:** [notebooks/01_devcontainer_setup.ipynb](../notebooks/01_devcontainer_setup.ipynb) — run Sections 1–2 to verify the Dev Container and check all tools are present.

The project includes a Dev Container configuration at `.devcontainer/devcontainer.json` that provides a consistent, pre-configured development environment.

**VS Code:**

1. Open the repository folder in VS Code
2. When prompted "Reopen in Container", click **Reopen in Container**
   — or open the Command Palette (`Ctrl+Shift+P`) → **Dev Containers: Reopen in Container**
3. Wait for the container to build and start — dependencies install automatically via `postCreateCommand`

**CLI (devcontainer CLI):**

```bash
# Install the CLI if not already available
npm install -g @devcontainers/cli

# Build and start
devcontainer up --workspace-folder .

# Open a shell inside
devcontainer exec --workspace-folder . bash
```

The Dev Container includes:
- Python 3.12 (base image: `mcr.microsoft.com/devcontainers/python:3.12-bookworm`)
- Docker-outside-of-Docker (uses the host's Docker daemon)
- Azure CLI
- VS Code extensions: Python, Pylance, Jupyter, Docker, YAML

---

## 2. Install Dependencies

> **Notebook:** [notebooks/01_devcontainer_setup.ipynb](../notebooks/01_devcontainer_setup.ipynb) — Section 2 runs the pip install and Section 3 verifies all imports, Section 4 validates project structure, Section 5 checks config.

Dependencies are installed automatically when the Dev Container starts (`postCreateCommand`). To install manually or after updating requirements files:

```bash
pip install -r requirements-local.txt
```

This installs the full development environment — `requirements.txt` (core ML), `requirements-infer.txt` (inference/API), plus dev tools like pytest, jupyter, and matplotlib.

### Requirements file roles

| File | Used by | Contents |
|---|---|---|
| `requirements.txt` | `Dockerfile.train`, CI pip-audit | Core ML — pandas, scikit-learn, numpy, joblib, pyyaml, azure-storage-blob |
| `requirements-infer.txt` | `Dockerfile.infer`, CI pip-audit | Inference API — fastapi, uvicorn, pydantic + subset of ML deps |
| `requirements-local.txt` | Dev Container `postCreateCommand`, CI install step | `-r requirements.txt` + `-r requirements-infer.txt` + dev tools (pytest, jupyter, black) |

### Updating dependencies

Files are manually maintained with **pinned versions** — this ensures the training image, inference image, and CI all use identical library versions.

To add or upgrade a package:

1. Install and test locally:
   ```bash
   pip install <package>==<version>
   ```
2. Add the pinned line to the appropriate file:
   - Training/pipeline dependency → `requirements.txt`
   - Inference/API dependency → `requirements-infer.txt`
   - Dev/test-only tool → `requirements-local.txt` (direct entry, not via `-r`)
3. Re-install to pick up the change:
   ```bash
   pip install -r requirements-local.txt
   ```
4. Run the test suite to confirm nothing breaks:
   ```bash
   pytest tests/
   ```

> **CI will fail** if `requirements.txt` or `requirements-infer.txt` contain packages with known CVEs — a `pip-audit` step runs on every PR and push to `main`.

Key packages:
| Package | Purpose |
|---|---|
| `pandas`, `scikit-learn`, `numpy` | ML pipeline |
| `fastapi`, `uvicorn`, `pydantic` | API serving |
| `pytest` | Test framework |
| `joblib` | Model serialisation |
| `pyyaml` | Config parsing |

---

## 3. Add the Dataset

> **Notebook:** [notebooks/01_devcontainer_setup.ipynb](../notebooks/01_devcontainer_setup.ipynb) — Section 6 verifies the dataset is in place.

The raw dataset is **not committed to the repository** (excluded via `.gitignore`). Place your CSV file in the expected location before training:

```
data/raw/bank_marketing_data.csv
```

The file must be semicolon-delimited (`;`) with the first column as the row index — this matches the `config.yaml` settings:

```yaml
data:
  raw_path: data/raw/bank_marketing_data.csv
  separator: ";"
  index_col: 0
```

Verify the file is present:

```bash
ls -lh data/raw/bank_marketing_data.csv
head -2 data/raw/bank_marketing_data.csv
```

---

## 4. Run the ML Pipeline

> **Notebook:** [notebooks/03_ml_pipeline.ipynb](../notebooks/03_ml_pipeline.ipynb) — Sections 1–3 train the model, inspect the artifact, and run batch predictions.

> **Important:** Ensure the dataset is in place first (see [Section 3](#3-add-the-dataset)).

### Train

Run the full training pipeline — loads data, engineers features, trains the model, evaluates, and saves artifacts:

```bash
python main.py train
```

**Outputs:**
- `artifacts/model.pkl` — trained sklearn Pipeline (preprocessor + classifier)
- `artifacts/metrics.json` — evaluation metrics (ROC-AUC, F1, etc.)

### Batch Predict

Generate predictions on a CSV file using the trained model:

```bash
# Print predictions to stdout
python main.py predict --input data/raw/bank_marketing_data.csv

# Save predictions to a file
python main.py predict --input data/raw/bank_marketing_data.csv --output data/results/predictions.csv
```

> **Note:** `python main.py train` must be run first to create `artifacts/model.pkl`.

---

## 5. Environment Variables

All environment variables have safe defaults for local development. Override them when switching backends or running in CI/CD.

> **Local vs Cloud:** In the CI/CD pipeline, the training job always runs against the local filesystem (`STORAGE_BACKEND=local`). Trained artifacts are then uploaded to Blob Storage via the `az` CLI — not through the Python storage module. `STORAGE_BACKEND=azure_blob` is set only by the **inference pod** (via [k8s/deployment.yaml](../k8s/deployment.yaml)) so it can pull `model.pkl` from Blob at startup. Cloud pipeline variables are managed in the `bank-marketing-vars` variable group in Azure DevOps — not set here.

### Storage backend

| Variable | Default | Scope | Purpose |
|---|---|---|---|
| `STORAGE_BACKEND` | `local` | Local + inference pod | `local` for filesystem; `azure_blob` for Blob Storage. CI training always uses `local`. |
| `AZURE_STORAGE_CONNECTION_STRING` | _(unset)_ | Local dev only | Blob auth — takes priority over managed identity. Use this when testing blob reads/writes locally. |
| `AZURE_STORAGE_ACCOUNT_NAME` | _(unset)_ | AKS inference pod | Blob auth for pods using AKS managed identity. Set via K8s secret in `deployment.yaml`. |
| `AZURE_STORAGE_CONTAINER` | _(unset)_ | Local + inference pod | Blob container name — required when `STORAGE_BACKEND=azure_blob`. |
| `MODEL_BLOB_PREFIX` | _(unset)_ | Inference pod | Prefix for blob model path. `staging` → `staging/artifacts/model.pkl`; `production` → `production/artifacts/model.pkl`. Set in `deployment.yaml`. |

**Local development (default — no config needed):**
```bash
python main.py train   # reads/writes to artifacts/ on local filesystem
```

**Test local code against Azure Blob Storage** (e.g. verifying blob reads work before deploying):
```bash
export STORAGE_BACKEND=azure_blob
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
export AZURE_STORAGE_CONTAINER=mlops-artifacts
python main.py train
```

> **In the CI/CD pipeline**, the training stage does not set `STORAGE_BACKEND`. It trains with `STORAGE_BACKEND=local` (default) and uploads artifacts to Blob Storage using `az storage blob upload`. Only the inference pod (`k8s/deployment.yaml`) sets `STORAGE_BACKEND=azure_blob`.

### Model path override

| Variable | Default | Scope | Purpose |
|---|---|---|---|
| `MODEL_PATH` | value from `config.yaml` `artifacts.model_path` | Local dev only | Override the model artifact path locally without editing config. Not used in cloud — `MODEL_BLOB_PREFIX` handles staging/production path separation in AKS. |

Useful locally for pointing at a specific artifact version:
```bash
export MODEL_PATH=artifacts/model_v2.pkl
python -m uvicorn src.api.app:app
```

### API server settings

| Variable | Default | Purpose |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Bind address for the FastAPI server |
| `API_PORT` | `8000` | Port the server listens on |
| `UVICORN_WORKERS` | `1` | Number of uvicorn worker processes |

---

## 6. Run Tests with pytest

> **Notebook:** [notebooks/03_ml_pipeline.ipynb](../notebooks/03_ml_pipeline.ipynb) — Sections 4–5 run the full test suite and individual test modules. Section 6 provides direct model inference for debugging.

The project uses pytest with fixtures defined in `tests/conftest.py`. A trained model artifact (`artifacts/model.pkl`) is required for API tests.

```bash
# Run all tests with verbose output
python -m pytest tests/ -v --tb=short
```

Run specific test modules:

```bash
# Config loading tests
python -m pytest tests/test_config.py -v

# Data loading tests
python -m pytest tests/test_data.py -v

# Feature engineering tests
python -m pytest tests/test_features.py -v

# API endpoint tests (requires artifacts/model.pkl)
python -m pytest tests/test_api.py -v
```

### Test Coverage

| Module | Tests |
|---|---|
| `test_config.py` | Config loading, required keys, value parsing, missing file handling |
| `test_data.py` | DataFrame loading, row counts, column validation, missing file handling |
| `test_features.py` | Cleaning transforms, split sizes, target encoding, preprocessor construction |
| `test_api.py` | `/health` endpoint, `/predict` responses, field validation, label consistency |

---

## 7. Validate K8s Manifests (kubeconform)

> **Notebook:** [notebooks/05_kubernetes_setup.ipynb](../notebooks/05_kubernetes_setup.ipynb) — Section 5 installs kubeconform and validates all `k8s/` manifests.

[kubeconform](https://github.com/yannh/kubeconform) validates Kubernetes manifests against the official JSON schemas — the same check that runs in CI.

### Install

```bash
curl -sLO https://github.com/yannh/kubeconform/releases/latest/download/kubeconform-linux-amd64.tar.gz
tar xzf kubeconform-linux-amd64.tar.gz
sudo mv kubeconform /usr/local/bin/
rm -f kubeconform-linux-amd64.tar.gz LICENSE
```

### Validate Manifests

```bash
# Validate all YAML files in the k8s/ directory
kubeconform -summary -strict k8s/

# Validate a specific file
kubeconform -strict k8s/deployment.yaml

# Validate with verbose output (shows each resource checked)
kubeconform -summary -strict -verbose k8s/
```

Expected output for valid manifests:
```
Summary: 2 resources found parsing k8s/ - Valid: 2, Invalid: 0, Errors: 0, Skipped: 0
```

### What kubeconform Catches

| Check | Example |
|---|---|
| YAML syntax errors | Missing colons, bad indentation |
| Invalid field names | `replics` instead of `replicas` |
| Wrong field types | `replicas: "2"` (string instead of int) |
| Missing required fields | Deployment without `selector` |

> **Note:** kubeconform performs client-side schema validation only. It does not check cluster-specific constraints like admission policies or resource quotas — those require `kubectl --dry-run=server` against a live cluster (see [Section 10](#10-local-kubernetes-setup)).

---

## 8. Set Up Docker Locally

> **Notebook:** [notebooks/04_docker_testing.ipynb](../notebooks/04_docker_testing.ipynb) — Section 1 verifies Docker access and troubleshoots common issues.

The Dev Container is configured with **Docker-outside-of-Docker**, meaning the Docker CLI inside the container communicates with the Docker daemon on your host machine. No additional setup is required if Docker Desktop is running on the host.

### Verify Docker Access

```bash
# Confirm the Docker CLI can reach the daemon
docker info

# Check running containers
docker ps
```

### Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop not running on host | Start Docker Desktop on the host machine |
| `permission denied` | Socket permissions | Restart the Dev Container — the feature configures socket access on startup |
| `docker: command not found` | Feature not installed | Rebuild the Dev Container (`Dev Containers: Rebuild Container`) |

---

## 9. Docker Build

> **Notebook:** [notebooks/04_docker_testing.ipynb](../notebooks/04_docker_testing.ipynb) — Sections 2–6 build and test the training container; Sections 7–13 build and test the inference container.

This project uses a **dual-container architecture**: a training container (`Dockerfile.train`) that produces `model.pkl`, and an inference container (`Dockerfile.infer`) that loads the model at runtime via a mounted volume. The local build mirrors the CI pipeline flow.

### Build the Training Image

```bash
docker build -f Dockerfile.train -t bank-marketing-train:local .
```

### Run Training to Produce model.pkl

```bash
mkdir -p artifacts
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/artifacts:/app/artifacts \
  bank-marketing-train:local
```

This mounts `data/` (input) and `artifacts/` (output) from your workspace. After the run, `artifacts/model.pkl` and `artifacts/metrics.json` are available on your local file system.

### Validate Training Container Output

After running the training container, validate the artifacts before proceeding to the inference image build:

```bash
# Check metrics.json has expected keys and values
python3 -c "
import json, joblib

# Validate metrics
with open('artifacts/metrics.json') as f:
    m = json.load(f)
for key in ['model_type', 'test_size', 'roc_auc', 'f1_minority_class', 'f1_macro']:
    assert key in m, f'Missing key: {key}'
assert 0 < m['roc_auc'] <= 1, f'roc_auc out of range: {m[\"roc_auc\"]}'
print('metrics.json valid:', m)

# Validate model is loadable
pipeline = joblib.load('artifacts/model.pkl')
assert hasattr(pipeline, 'predict'), 'Model has no predict method'
assert hasattr(pipeline, 'predict_proba'), 'Model has no predict_proba method'
print(f'model.pkl valid: {[name for name, _ in pipeline.steps]}')
"
```

### Verify Training Reproducibility

Re-run the training container and confirm metrics are identical (fixed `random_state` in `config.yaml` ensures determinism):

```bash
# Run training twice and compare metrics
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/artifacts:/app/artifacts \
  bank-marketing-train:local

cat artifacts/metrics.json
# Metrics should be identical to the first run
```

### Build the Inference Image

The inference image does **not** contain `model.pkl` — the model is loaded at runtime via a mounted volume (local) or Azure Blob Storage (AKS):

```bash
docker build -f Dockerfile.infer -t bank-marketing-api:local .
```

> `artifacts/model.pkl` must exist on the host for the volume mount to work when running the container.

### Verify Images

```bash
docker images | grep bank-marketing
```

### Build Tips

| Flag | Purpose | Example |
|---|---|---|
| `-f` | Specify Dockerfile | `-f Dockerfile.train` or `-f Dockerfile.infer` |
| `-t` | Tag the image | `-t bank-marketing-api:local` |
| `--no-cache` | Force a clean rebuild | `docker build --no-cache -f Dockerfile.infer -t bank-marketing-api:local .` |
| `--progress=plain` | Show full build output | Useful for debugging failed builds |

---

## 10. Local Container Smoke Test

> **Notebook:** [notebooks/04_docker_testing.ipynb](../notebooks/04_docker_testing.ipynb) — Sections 8–13 run the inference container, health check, prediction tests, edge cases, scripted pass/fail smoke test, log inspection, and cleanup.

Run the inference image (built in [Section 8](#8-docker-build)) and verify the API starts correctly and responds to requests.

### Start the Container

> **DooD networking:** In Docker-outside-of-Docker, `-p 8000:8000` publishes to the *host machine's* localhost — not reachable via `curl` from inside the devcontainer. Use `--network container:$(hostname)` to share the devcontainer's network namespace instead.

> **API key authentication:** The `/predict` endpoint requires an `X-API-Key` header when the `API_KEY` env var is set. Pass `-e API_KEY=<key>` to the container and include `-H "X-API-Key: <key>"` in prediction requests. The `/health` endpoint remains unauthenticated (required for K8s probes).

```bash
docker run -d --name smoke-test --network container:$(hostname) \
  -v $(pwd)/artifacts:/app/artifacts:ro \
  -e API_KEY=test-local-key \
  bank-marketing-api:local
```

### Run Smoke Tests

```bash
# Wait for the container to start (model loading)
sleep 5

# Health check
curl -s http://localhost:8000/health
# Expected: {"status":"healthy"}

# Prediction request
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-local-key" \
  -d '{
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
    "poutcome": "unknown"
  }'
# Expected: {"prediction":...,"probability":...,"label":"..."}

# Check container logs for errors
docker logs smoke-test
```

### Clean Up

```bash
docker stop smoke-test
docker rm smoke-test
```

### Scripted Smoke Test

Combine health check and prediction into a single pass/fail script:

```bash
#!/bin/bash
set -e

echo "Starting container..."
docker run -d --name smoke-test --network container:$(hostname) \
  -v $(pwd)/artifacts:/app/artifacts:ro \
  -e API_KEY=test-local-key \
  bank-marketing-api:local
sleep 5

echo "Health check..."
HEALTH=$(curl -sf http://localhost:8000/health)
echo "$HEALTH" | grep -q '"healthy"' || { echo "FAIL: health check"; exit 1; }

echo "Prediction test..."
PRED=$(curl -sf -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-local-key" \
  -d '{"age":35,"job":"management","marital":"married","education":"tertiary","default":"no","balance":1500.0,"housing":"yes","loan":"no","contact":"cellular","day":15,"month":"may","duration":250.0,"campaign":1,"pdays":-1,"previous":0,"poutcome":"unknown"}')
echo "$PRED" | grep -q '"prediction"' || { echo "FAIL: predict endpoint"; exit 1; }

echo "PASS: All smoke tests passed"
echo "Response: $PRED"

docker stop smoke-test && docker rm smoke-test
```

---

## 11. Local Kubernetes Setup

> **Notebook:** [notebooks/05_kubernetes_setup.ipynb](../notebooks/05_kubernetes_setup.ipynb) — run top-to-bottom to install kubectl/kind, bootstrap the cluster, deploy to both namespaces, validate the ResourceQuota, and simulate the CD_Dev smoke test.

For validating Kubernetes manifests and testing deployments locally without an AKS cluster.

> **Note:** This project runs inside a Dev Container (nested Docker). `minikube` is not suitable here — its SSH-based bootstrap times out in nested Docker environments. [`kind`](https://kind.sigs.k8s.io/) (Kubernetes IN Docker) is the correct tool for this setup: it runs Kubernetes entirely via the Docker API with no SSH dependency.

### Install kubectl

```bash
# Download the latest stable release
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Install
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client
```

### Install and Start kind

```bash
# Download and install kind
curl -Lo /tmp/kind https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64
chmod +x /tmp/kind
sudo mv /tmp/kind /usr/local/bin/kind

# Verify
kind version

# Create a single-node cluster
# --retain is required in DooD: without it, kind deletes the node when its localhost
# readiness check times out, preventing manual bootstrap (admin.conf missing error).
kind create cluster --config kind-config.yaml --retain
```

> **DooD networking note:** In a Docker-outside-of-Docker devcontainer, `kind create cluster` always exits with an error (either `connection refused` or `failed to remove control plane taint: stat /etc/kubernetes/admin.conf: no such file or directory`). This is not a real failure — kubeadm and the API server complete successfully inside the container. The error occurs because kind verifies readiness by connecting to `localhost:<port>`, which resolves to the devcontainer's own localhost, not the host where the kind node port is published. Without `--retain`, kind deletes the node before you can manually bootstrap, producing the `admin.conf` missing error. With `--retain`, the node survives and the cluster is fully usable via the steps below.

```bash
# Export kubeconfig (ignore any error about the cluster not being ready)
kind export kubeconfig --name bm-local

# Get the kind node's Docker-network IP
NODE_IP=$(docker inspect bm-local-control-plane \
  --format '{{.NetworkSettings.Networks.kind.IPAddress}}')
echo "Node IP: $NODE_IP"

# Patch kubeconfig to use the container's internal IP instead of localhost
kubectl config set-cluster kind-bm-local --server=https://${NODE_IP}:6443

# Install the bundled CNI plugin
# kind can't do this itself due to DooD — the manifest is baked into the node image
docker exec bm-local-control-plane cat /kind/manifests/default-cni.yaml \
  | sed 's/{{ .PodSubnet }}/10.244.0.0\/24/' \
  | kubectl apply -f -

# Install the default storage class
docker exec bm-local-control-plane cat /kind/manifests/default-storage.yaml \
  | kubectl apply -f -

# Remove the control-plane taint so workload pods can schedule on the single node
# (kind normally does this automatically, but the DooD error prevents it)
kubectl taint nodes --all node-role.kubernetes.io/control-plane- 2>/dev/null || true

# Wait for node to become Ready (usually < 30 s)
kubectl wait --for=condition=Ready node --all --timeout=120s

# Verify
kubectl cluster-info --context kind-bm-local
kubectl get nodes
```

### Two-Namespace Local Setup

The AKS cluster uses two namespaces — `bank-marketing` (production inference, deployed from `main`) and `bank-marketing-dev` (staging inference, deployed from `dev`). The local kind cluster mirrors this structure exactly. Model training runs as a `docker run` on the CI agent (or locally) — not as a Kubernetes workload.

```
kind cluster: bm-local
├── namespace: bank-marketing            ← production inference  (k8s/deployment.yaml + k8s/service.yaml)
└── namespace: bank-marketing-dev        ← staging inference     (k8s/deployment-dev.yaml + k8s/service-dev.yaml + k8s/quota-dev.yaml)
```

### Deploy Locally

Once you have built a Docker image (see [Section 8](#8-docker-build)), load it into the kind cluster and deploy to both namespaces.

> **Image override required:** The `k8s/deployment.yaml` and `k8s/deployment-dev.yaml` manifests reference ACR images (`bankmarketingacr.azurecr.io/bank-marketing-api:latest` and `:dev-latest`) because they are the source-of-truth for AKS deployments. The CI/CD pipeline substitutes the correct image tag at deploy time via the `KubernetesManifest@1` task's `containers:` input — the YAML files themselves are never modified in Git.
>
> In kind there is no ACR registry, so pods will stay in **Pending** (with `ErrImageNeverPull` or `ImagePullBackOff`) unless you override the image after applying the manifests. **Do not edit the YAML files** — the ACR references are correct for production.
>
> **Why scale to 0 before patching:** `kubectl apply` immediately creates pods that try (and fail) to pull the ACR image. Those pods get scheduled to the node and consume resource requests even while stuck in `ImagePullBackOff`. If you then run `kubectl set image` or `kubectl patch`, each triggers a *separate* new rollout. The default RollingUpdate strategy (`maxUnavailable: 0`) refuses to terminate old pods until replacements are Ready — but the new pods can't schedule because the stuck ones still hold the node's resources. This creates a **deadlock** and the rollout times out. Scaling to 0 first clears all stuck pods from the node, the patch applies cleanly to the Deployment spec, and scaling back up creates pods with the correct image from the start — a single clean rollout.

```bash
# Load local image into kind (avoids needing a registry)
# A single local image is used for both namespaces — on AKS, dev-<buildId> and <buildId> are separate ACR tags
kind load docker-image bank-marketing-api:local --name bm-local

# Create both namespaces
kubectl create namespace bank-marketing
kubectl create namespace bank-marketing-dev

# Create API key secrets in both namespaces (required for /predict authentication)
kubectl create secret generic bank-marketing-api-key \
  --from-literal=API_KEY=test-local-key -n bank-marketing
kubectl create secret generic bank-marketing-api-key \
  --from-literal=API_KEY=test-local-key -n bank-marketing-dev

# Create dummy azure-storage secret in production namespace
# (deployment.yaml references this for AKS managed identity — kind doesn't need real values)
kubectl create secret generic azure-storage \
  --from-literal=ACCOUNT_NAME=dummy \
  --from-literal=CONTAINER_NAME=dummy \
  -n bank-marketing

# Copy model artifact to the kind node (inference image loads it via hostPath at /app/artifacts)
docker exec bm-local-control-plane mkdir -p /tmp/bank-marketing/artifacts
cat artifacts/model.pkl | docker exec -i bm-local-control-plane \
  sh -c "cat > /tmp/bank-marketing/artifacts/model.pkl"

# --- Production namespace ---
# Apply manifests, then immediately scale to 0 to prevent stuck ACR-image pods
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -n bank-marketing
kubectl scale deployment/bank-marketing-api --replicas=0 -n bank-marketing

# JSON patch: override image, set STORAGE_BACKEND=local (not azure_blob),
# add hostPath volume mount for model.pkl, remove imagePullSecrets
kubectl patch deployment bank-marketing-api -n bank-marketing --type=json -p '[
  {"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "bank-marketing-api:local"},
  {"op": "add", "path": "/spec/template/spec/containers/0/imagePullPolicy", "value": "Never"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/env", "value": [
    {"name": "UVICORN_WORKERS", "value": "1"},
    {"name": "API_KEY", "valueFrom": {"secretKeyRef": {"name": "bank-marketing-api-key", "key": "API_KEY"}}},
    {"name": "STORAGE_BACKEND", "value": "local"}
  ]},
  {"op": "add", "path": "/spec/template/spec/containers/0/volumeMounts", "value": [
    {"name": "model-artifacts", "mountPath": "/app/artifacts", "readOnly": true}
  ]},
  {"op": "add", "path": "/spec/template/spec/volumes", "value": [
    {"name": "model-artifacts", "hostPath": {"path": "/tmp/bank-marketing/artifacts", "type": "DirectoryOrCreate"}}
  ]},
  {"op": "remove", "path": "/spec/template/spec/imagePullSecrets"}
]'

# Scale back up — pods start with the correct local image from the outset
kubectl scale deployment/bank-marketing-api --replicas=2 -n bank-marketing

# --- Staging namespace ---
# Apply manifests, then immediately scale to 0
kubectl apply -f k8s/quota-dev.yaml -n bank-marketing-dev
kubectl apply -f k8s/deployment-dev.yaml -f k8s/service-dev.yaml -n bank-marketing-dev
kubectl scale deployment/bank-marketing-api --replicas=0 -n bank-marketing-dev

# Same JSON patch for staging (dev manifest also references azure-storage and imagePullSecrets)
kubectl patch deployment bank-marketing-api -n bank-marketing-dev --type=json -p '[
  {"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "bank-marketing-api:local"},
  {"op": "add", "path": "/spec/template/spec/containers/0/imagePullPolicy", "value": "Never"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/env", "value": [
    {"name": "UVICORN_WORKERS", "value": "1"},
    {"name": "API_KEY", "valueFrom": {"secretKeyRef": {"name": "bank-marketing-api-key", "key": "API_KEY"}}},
    {"name": "STORAGE_BACKEND", "value": "local"}
  ]},
  {"op": "add", "path": "/spec/template/spec/containers/0/volumeMounts", "value": [
    {"name": "model-artifacts", "mountPath": "/app/artifacts", "readOnly": true}
  ]},
  {"op": "add", "path": "/spec/template/spec/volumes", "value": [
    {"name": "model-artifacts", "hostPath": {"path": "/tmp/bank-marketing/artifacts", "type": "DirectoryOrCreate"}}
  ]},
  {"op": "remove", "path": "/spec/template/spec/imagePullSecrets"}
]'

# Scale back up
kubectl scale deployment/bank-marketing-api --replicas=1 -n bank-marketing-dev

# Wait for both rollouts to complete
kubectl rollout status deployment/bank-marketing-api -n bank-marketing --timeout=120s
kubectl rollout status deployment/bank-marketing-api -n bank-marketing-dev --timeout=120s

# Verify pods are running in both namespaces
kubectl get pods -n bank-marketing
kubectl get pods -n bank-marketing-dev

# Check services (production: LoadBalancer pending; staging: ClusterIP with cluster IP assigned)
kubectl get svc -n bank-marketing
kubectl get svc -n bank-marketing-dev
```

> **Troubleshooting Pending pods:** If pods stay in `Pending` for more than 30 seconds, run `kubectl describe pod <pod-name> -n <namespace>` and check the `Events` section at the bottom. Common causes in kind:
> - `ErrImageNeverPull` / `ImagePullBackOff` — the image override was not applied, or `kind load docker-image` was not run
> - `Insufficient cpu` / `Insufficient memory` — the node lacks resources (unlikely on the default single-node kind cluster unless other workloads are competing)
> - **Rollout deadlock** — if you ran `kubectl set image` or `kubectl patch` without scaling to 0 first, old stuck pods block new ones. Fix with: `kubectl scale deployment/bank-marketing-api --replicas=0 -n <namespace>`, wait a few seconds, then `kubectl scale deployment/bank-marketing-api --replicas=<N> -n <namespace>`
> - `untolerated taint {node-role.kubernetes.io/control-plane}` — the taint removal step was skipped; run `kubectl taint nodes --all node-role.kubernetes.io/control-plane-`

### Redeploying After Image Rebuild

After rebuilding the Docker image (e.g. code change), re-deploy with the **scale-to-0 pattern** — do **not** use `kubectl rollout restart`, which triggers a RollingUpdate that deadlocks for the same reason as above (old pods hold resources while new pods wait to schedule).

```bash
kind load docker-image bank-marketing-api:local --name bm-local
kubectl scale deployment/bank-marketing-api --replicas=0 -n bank-marketing
kubectl scale deployment/bank-marketing-api --replicas=0 -n bank-marketing-dev
sleep 3
kubectl scale deployment/bank-marketing-api --replicas=2 -n bank-marketing
kubectl scale deployment/bank-marketing-api --replicas=1 -n bank-marketing-dev
kubectl rollout status deployment/bank-marketing-api -n bank-marketing --timeout=120s
kubectl rollout status deployment/bank-marketing-api -n bank-marketing-dev --timeout=120s
```

> **Note on service types in kind:**
> - `k8s/service.yaml` (production) uses `type: LoadBalancer` — on AKS this provisions an Azure Load Balancer. In kind it stays in `<pending>` state. Use `kubectl port-forward` to access it locally.
> - `k8s/service-dev.yaml` (staging) uses `type: ClusterIP` — this is the correct type for the staging service in both kind and AKS. It is accessed via `kubectl port-forward` or `kubectl exec` locally, and via `kubectl exec` in the CI pipeline smoke test.

### Access the Services Locally

```bash
# Production namespace — port-forward the LoadBalancer service
kubectl port-forward svc/bank-marketing-api 8000:80 -n bank-marketing
# API accessible at http://localhost:8000

# Staging namespace — port-forward the ClusterIP service
kubectl port-forward svc/bank-marketing-api 8001:8000 -n bank-marketing-dev
# Staging API accessible at http://localhost:8001
```

### Simulating the CD_Dev Smoke Test Locally

The CI pipeline (`CD_Dev` stage) validates the staging namespace by running a `kubectl exec` command against the deployed pod — not via a port-forward. You can replicate this locally to confirm the smoke test will pass on AKS:

```bash
# Wait for the staging pod to be ready
kubectl wait --for=condition=ready pod \
  -l app=bank-marketing-api \
  -n bank-marketing-dev \
  --timeout=120s

# Run health check from inside the pod (mirrors what CD_Dev does in AKS)
kubectl exec -n bank-marketing-dev \
  deploy/bank-marketing-api -- \
  curl -sf http://localhost:8000/health

# Run a prediction from inside the pod
kubectl exec -n bank-marketing-dev \
  deploy/bank-marketing-api -- \
  curl -sf -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"age":35,"job":"management","marital":"married","education":"tertiary","default":"no","balance":1500.0,"housing":"yes","loan":"no","contact":"cellular","day":15,"month":"may","duration":250.0,"campaign":1,"pdays":-1,"previous":0,"poutcome":"unknown"}'
```

If these commands pass locally, the equivalent `CD_Dev` stage will pass on AKS.

### Verify ResourceQuota

Confirm the staging `ResourceQuota` is enforced correctly:

```bash
# View quota usage in the staging namespace
kubectl describe resourcequota bank-marketing-dev-quota -n bank-marketing-dev
```

Expected output shows `Used` values at or below `Hard` limits. If a second pod is attempted (e.g. a manual `kubectl run`), it should be rejected by the quota.

### Clean Up

```bash
# Delete resources from all namespaces
kubectl delete -f k8s/deployment.yaml -f k8s/service.yaml -n bank-marketing
kubectl delete -f k8s/deployment-dev.yaml -f k8s/service-dev.yaml -f k8s/quota-dev.yaml -n bank-marketing-dev

# Or delete the cluster entirely
kind delete cluster --name bm-local
```

### Moving to AKS

Once both namespace configurations are validated locally with kind, deploying to AKS requires only a context switch — the `kubectl apply` commands are identical. The key difference is that on AKS, images come from ACR rather than the local kind image cache:

```bash
# Authenticate to AKS and update your local kubeconfig
az aks get-credentials --resource-group rg-bank-marketing --name bank-marketing-aks

# Confirm you are now targeting AKS
kubectl config current-context

# Create namespaces on AKS (if not already present)
kubectl create namespace bank-marketing --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace bank-marketing-dev --dry-run=client -o yaml | kubectl apply -f -

# Apply production manifests (image must reference ACR tag: bankmarketingacr.azurecr.io/bank-marketing-api:<buildId>)
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -n bank-marketing

# Apply staging manifests (image: bankmarketingacr.azurecr.io/bank-marketing-api:dev-<buildId>)
kubectl apply -f k8s/quota-dev.yaml -n bank-marketing-dev
kubectl apply -f k8s/deployment-dev.yaml -f k8s/service-dev.yaml -n bank-marketing-dev

# Switch back to kind for local development
kubectl config use-context kind-bm-local
```

> **Note:** Before applying to AKS, update the `image:` fields in `k8s/deployment.yaml` and `k8s/deployment-dev.yaml` to point to ACR (e.g. `bankmarketingacr.azurecr.io/bank-marketing-api:latest` and `bankmarketingacr.azurecr.io/bank-marketing-api:dev-latest`) rather than the local `bank-marketing-api:local` tag used in kind. In practice the CI/CD pipeline manages this substitution automatically via the `KubernetesManifest@1` task's `containers:` input.

---

## 12. Local Inference Call Tests

> **Notebook:** [notebooks/03_ml_pipeline.ipynb](../notebooks/03_ml_pipeline.ipynb) — Section 6 tests direct model inference without starting the API server. For full API inference over HTTP, use `04_docker_testing.ipynb`.

Test the prediction API locally without Docker, using `uvicorn` directly.

### Start the API Server

```bash
# Ensure the model artifact exists
python main.py train

# Start the API
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

The server starts and loads `artifacts/model.pkl` at startup. You should see:

```
INFO:     Loading model artifact...
INFO:     Model loaded — ready to serve.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Test Endpoints

**Health check:**

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

```json
{
    "status": "healthy"
}
```

**Single prediction:**

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
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
    "poutcome": "unknown"
  }' | python3 -m json.tool
```

```json
{
    "prediction": 0,
    "probability": 0.1234,
    "label": "no"
}
```

**Validation error (missing field):**

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age": 35, "job": "management"}' | python3 -m json.tool
```

Returns HTTP 422 with details on the missing required fields.

**OpenAPI docs:**

Open `http://localhost:8000/docs` in a browser for the auto-generated interactive API documentation. Use this to explore the request schema and test predictions directly from the browser.

### Test with Python

```python
import requests

url = "http://localhost:8000/predict"
payload = {
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

response = requests.post(url, json=payload)
print(response.status_code)  # 200
print(response.json())       # {"prediction": ..., "probability": ..., "label": "..."}
```

### Edge Cases to Test

| Scenario | Input | Expected |
|---|---|---|
| Young customer | `"age": 18` | Valid prediction |
| High balance | `"balance": 100000.0` | Valid prediction |
| Negative balance | `"balance": -500.0` | Valid prediction (signed-log handles negatives) |
| Unknown poutcome | `"poutcome": "unknown"` | Valid prediction |
| Missing field | Omit `age` | HTTP 422 |
| Wrong type | `"age": "thirty"` | HTTP 422 |
| Empty body | `{}` | HTTP 422 |

---

## Quick Reference

| Task | Command |
|---|---|
| Install dependencies | `pip install -r requirements-local.txt` |
| Train model | `python main.py train` |
| Batch predict | `python main.py predict --input <csv> --output <csv>` |
| Run all tests | `python -m pytest tests/ -v --tb=short` |
| Validate K8s manifests | `kubeconform -summary -strict k8s/` |
| Start API server | `uvicorn src.api.app:app --host 0.0.0.0 --port 8000` |
| Build training image | `docker build -f Dockerfile.train -t bank-marketing-train:local .` |
| Run training container | `docker run --rm -v $(pwd)/data:/app/data -v $(pwd)/artifacts:/app/artifacts bank-marketing-train:local` |
| Build inference image | `docker build -f Dockerfile.infer -t bank-marketing-api:local .` |
| Run inference container | `docker run -d --name smoke-test --network container:$(hostname) bank-marketing-api:local` |
| Health check | `curl -s http://localhost:8000/health` |
| Predict request | `curl -s -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{...}'` |
| Start kind cluster | `kind create cluster --config kind-config.yaml --retain` (see DooD note in Section 10) |
| Load image into kind | `kind load docker-image bank-marketing-api:local --name bm-local` |
| Create namespaces | `kubectl create namespace bank-marketing && kubectl create namespace bank-marketing-dev` |
| Deploy to production namespace | `kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -n bank-marketing` |
| Deploy to staging namespace | `kubectl apply -f k8s/quota-dev.yaml -f k8s/deployment-dev.yaml -f k8s/service-dev.yaml -n bank-marketing-dev` |
| Port-forward production | `kubectl port-forward svc/bank-marketing-api 8000:80 -n bank-marketing` |
| Port-forward staging | `kubectl port-forward svc/bank-marketing-api 8001:8000 -n bank-marketing-dev` |
| Simulate CD_Dev smoke test | `kubectl exec -n bank-marketing-dev deploy/bank-marketing-api -- curl -sf http://localhost:8000/health` |
| Check ResourceQuota usage | `kubectl describe resourcequota bank-marketing-dev-quota -n bank-marketing-dev` |
| Delete kind cluster | `kind delete cluster --name bm-local` |
| Switch kubectl to AKS | `az aks get-credentials --resource-group rg-bank-marketing --name bank-marketing-aks` |
| Switch kubectl to kind | `kubectl config use-context kind-bm-local` |

---

## Key References

### Dev Containers

- Microsoft. [Development Containers Specification](https://containers.dev/). Defines the `devcontainer.json` schema, lifecycle hooks (`postCreateCommand`), and feature references used in this project's Dev Container configuration.
- Microsoft. [Dev Containers tutorial — VS Code](https://code.visualstudio.com/docs/devcontainers/tutorial). Walkthrough for opening a project in a Dev Container from VS Code — covers the "Reopen in Container" workflow described in Section 1.
- Microsoft. [Dev Container Features — Docker-outside-of-Docker](https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker). Reference for the `ghcr.io/devcontainers/features/docker-outside-of-docker:1` feature that provides Docker CLI access inside the Dev Container using the host's Docker daemon.
- Microsoft. [Dev Container CLI](https://github.com/devcontainers/cli). The `devcontainer up` and `devcontainer exec` CLI commands used for headless Dev Container startup.

### Python & Testing

- pytest. [How to invoke pytest](https://docs.pytest.org/en/stable/how-to/usage.html). Official reference for `pytest` invocation patterns, `-v`, `--tb=short`, and module-level test selection used throughout Section 5.
- FastAPI. [Testing — FastAPI](https://fastapi.tiangolo.com/tutorial/testing/). Documents the `TestClient` pattern used in `tests/test_api.py` for testing endpoints without a running server.
- Uvicorn. [Running Uvicorn](https://www.uvicorn.org/#usage). Reference for the `uvicorn src.api.app:app --host --port` command used to start the API server locally in Section 11.

### Docker

- Docker. [Dockerfile reference](https://docs.docker.com/reference/dockerfile/). Canonical reference for `FROM`, `COPY`, `RUN`, `EXPOSE`, and `CMD` instructions used in the example Dockerfile in Section 7.
- Docker. [docker build](https://docs.docker.com/reference/cli/docker/image/build/). CLI reference for `docker build -t`, `--no-cache`, and `--progress` flags documented in Section 7.
- Docker. [docker run](https://docs.docker.com/reference/cli/docker/container/run/). CLI reference for `-d`, `--name`, `--network`, and container lifecycle commands used in Sections 8 and 10.

### Kubernetes

- Kubernetes. [Install kubectl — Linux](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/). Official install instructions for `kubectl` on Linux, referenced in Section 9.
- kind. [Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/). Official installation and cluster creation guide — covers `kind create cluster`, kubeconfig setup, and cluster lifecycle commands used in Section 9.
- kind. [Loading an image into a cluster](https://kind.sigs.k8s.io/docs/user/quick-start/#loading-an-image-into-your-cluster). Documents the `kind load docker-image` command used to load locally-built images into the kind cluster without a registry.
- kind. [Known issues — WSL2](https://kind.sigs.k8s.io/docs/user/known-issues/#pod-errors-due-to-too-many-open-files). Background on kind behaviour in containerised and WSL2 environments — relevant to the `cgroupDriver: cgroupfs` config in `kind-config.yaml`.
- yannh. [kubeconform — GitHub](https://github.com/yannh/kubeconform). Kubernetes manifest validator used in Section 5 — covers installation, `-strict` mode, and schema validation behaviour.
