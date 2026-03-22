# Local Development Guide

Step-by-step instructions for running and testing every component of the project locally — from environment setup through containerised smoke tests.

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

Dependencies are installed automatically when the Dev Container starts (`postCreateCommand`). To install manually or after updating `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages:
| Package | Purpose |
|---|---|
| `pandas`, `scikit-learn`, `numpy` | ML pipeline |
| `fastapi`, `uvicorn`, `pydantic` | API serving |
| `pytest` | Test framework |
| `joblib` | Model serialisation |
| `pyyaml` | Config parsing |

---

## 3. Run the ML Pipeline

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

## 4. Run Tests with pytest

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

## 5. Local Kubernetes Setup

For validating Kubernetes manifests and testing deployments locally without an AKS cluster.

### Install kubectl

```bash
# Download the latest stable release
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Install
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client
```

### Install and Start minikube

[minikube](https://minikube.sigs.k8s.io/) runs a single-node Kubernetes cluster locally inside Docker:

```bash
# Download and install
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Start a cluster (uses Docker driver inside the Dev Container)
minikube start --driver=docker

# Verify the cluster is running
kubectl cluster-info
kubectl get nodes
```

### Deploy Locally

Once you have built a Docker image (see [Section 8](#8-docker-build)), load it into minikube and apply manifests:

```bash
# Load local image into minikube (avoids needing a registry)
minikube image load bank-marketing-api:local

# Create namespace
kubectl create namespace bank-marketing

# Apply manifests (adjust image reference in deployment.yaml to bank-marketing-api:local)
kubectl apply -f k8s/ -n bank-marketing

# Verify pods are running
kubectl get pods -n bank-marketing

# Check service
kubectl get svc -n bank-marketing

# Access the service via minikube
minikube service bank-marketing-api -n bank-marketing --url
```

### Clean Up

```bash
# Delete the deployment
kubectl delete -f k8s/ -n bank-marketing

# Stop the cluster
minikube stop

# Delete the cluster entirely
minikube delete
```

---

## 6. Run kubeconform Locally

[kubeconform](https://github.com/yannh/kubeconform) validates Kubernetes manifests against the official JSON schemas — the same check that runs in CI.

### Install

```bash
curl -sLO https://github.com/yannh/kubeconform/releases/latest/download/kubeconform-linux-amd64.tar.gz
tar xzf kubeconform-linux-amd64.tar.gz
sudo mv kubeconform /usr/local/bin/
rm kubeconform-linux-amd64.tar.gz
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

> **Note:** kubeconform performs client-side schema validation only. It does not check cluster-specific constraints like admission policies or resource quotas — those require `kubectl --dry-run=server` against a live cluster (see [Section 5](#5-local-kubernetes-setup)).

---

## 7. Set Up Docker Locally

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

## 8. Docker Build

Build the container image locally. Since the project does not yet have a Dockerfile, create one at the repository root first.

### Example Dockerfile

> **Note:** This Dockerfile is based on the deployment architecture documented in [docs/deployment.md](deployment.md). Create it at the repository root as `Dockerfile`.

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config.yaml .
COPY artifacts/model.pkl artifacts/model.pkl

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build the Image

```bash
# Build with a local tag
docker build -t bank-marketing-api:local .

# Verify the image was created
docker images | grep bank-marketing-api
```

### Build Tips

| Flag | Purpose | Example |
|---|---|---|
| `-t` | Tag the image | `-t bank-marketing-api:local` |
| `--no-cache` | Force a clean rebuild | `docker build --no-cache -t bank-marketing-api:local .` |
| `--progress=plain` | Show full build output | Useful for debugging failed builds |

---

## 9. Local Container Smoke Test

Run the built image and verify the API starts correctly and responds to requests.

### Start the Container

```bash
docker run -d --name smoke-test -p 8000:8000 bank-marketing-api:local
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
docker run -d --name smoke-test -p 8000:8000 bank-marketing-api:local
sleep 5

echo "Health check..."
HEALTH=$(curl -sf http://localhost:8000/health)
echo "$HEALTH" | grep -q '"healthy"' || { echo "FAIL: health check"; exit 1; }

echo "Prediction test..."
PRED=$(curl -sf -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":35,"job":"management","marital":"married","education":"tertiary","default":"no","balance":1500.0,"housing":"yes","loan":"no","contact":"cellular","day":15,"month":"may","duration":250.0,"campaign":1,"pdays":-1,"previous":0,"poutcome":"unknown"}')
echo "$PRED" | grep -q '"prediction"' || { echo "FAIL: predict endpoint"; exit 1; }

echo "PASS: All smoke tests passed"
echo "Response: $PRED"

docker stop smoke-test && docker rm smoke-test
```

---

## 10. Local Inference Call Tests

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
| Install dependencies | `pip install -r requirements.txt` |
| Train model | `python main.py train` |
| Batch predict | `python main.py predict --input <csv> --output <csv>` |
| Run all tests | `python -m pytest tests/ -v --tb=short` |
| Start API server | `uvicorn src.api.app:app --host 0.0.0.0 --port 8000` |
| Build Docker image | `docker build -t bank-marketing-api:local .` |
| Run container | `docker run -d --name smoke-test -p 8000:8000 bank-marketing-api:local` |
| Health check | `curl -s http://localhost:8000/health` |
| Predict request | `curl -s -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{...}'` |
| Validate K8s manifests | `kubeconform -summary -strict k8s/` |
| Start minikube | `minikube start --driver=docker` |

---

## Key References

### Dev Containers

- Microsoft. [Development Containers Specification](https://containers.dev/). Defines the `devcontainer.json` schema, lifecycle hooks (`postCreateCommand`), and feature references used in this project's Dev Container configuration.
- Microsoft. [Dev Containers tutorial — VS Code](https://code.visualstudio.com/docs/devcontainers/tutorial). Walkthrough for opening a project in a Dev Container from VS Code — covers the "Reopen in Container" workflow described in Section 1.
- Microsoft. [Dev Container Features — Docker-outside-of-Docker](https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker). Reference for the `ghcr.io/devcontainers/features/docker-outside-of-docker:1` feature that provides Docker CLI access inside the Dev Container using the host's Docker daemon.
- Microsoft. [Dev Container CLI](https://github.com/devcontainers/cli). The `devcontainer up` and `devcontainer exec` CLI commands used for headless Dev Container startup.

### Python & Testing

- pytest. [How to invoke pytest](https://docs.pytest.org/en/stable/how-to/usage.html). Official reference for `pytest` invocation patterns, `-v`, `--tb=short`, and module-level test selection used throughout Section 4.
- FastAPI. [Testing — FastAPI](https://fastapi.tiangolo.com/tutorial/testing/). Documents the `TestClient` pattern used in `tests/test_api.py` for testing endpoints without a running server.
- Uvicorn. [Running Uvicorn](https://www.uvicorn.org/#usage). Reference for the `uvicorn src.api.app:app --host --port` command used to start the API server locally in Section 10.

### Docker

- Docker. [Dockerfile reference](https://docs.docker.com/reference/dockerfile/). Canonical reference for `FROM`, `COPY`, `RUN`, `EXPOSE`, and `CMD` instructions used in the example Dockerfile in Section 8.
- Docker. [docker build](https://docs.docker.com/reference/cli/docker/image/build/). CLI reference for `docker build -t`, `--no-cache`, and `--progress` flags documented in Section 8.
- Docker. [docker run](https://docs.docker.com/reference/cli/docker/container/run/). CLI reference for `-d`, `--name`, `-p` port mapping, and container lifecycle commands used in Sections 9 and 10.

### Kubernetes

- Kubernetes. [Install kubectl — Linux](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/). Official install instructions for `kubectl` on Linux, referenced in Section 5.
- minikube. [Get Started](https://minikube.sigs.k8s.io/docs/start/). Installation and `minikube start --driver=docker` command used for local cluster setup in Section 5.
- minikube. [Pushing images — minikube image load](https://minikube.sigs.k8s.io/docs/handbook/pushing/#7-loading-directly-to-in-cluster-container-runtime). Documents the `minikube image load` command used to load locally-built images into the minikube cluster without a registry.
- yannh. [kubeconform — GitHub](https://github.com/yannh/kubeconform). Kubernetes manifest validator used in Section 6 — covers installation, `-strict` mode, and schema validation behaviour.
