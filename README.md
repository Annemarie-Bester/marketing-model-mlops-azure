# Bank Marketing MLOps — ML Engineering Assessment

A production-grade ML system for predicting bank term deposit subscriptions.
Built to demonstrate MLOps engineering practices: reproducible pipelines, containerised deployment, CI/CD via Azure DevOps, and serving on AKS.

> **Problem statement**: Predict whether a customer will subscribe to a term deposit (`target = yes/no`) based on demographic and campaign interaction data.

---

## Quick Start

```bash
# 1. Clone and install dependencies
pip install -r requirements.txt

# 2. Run the full training pipeline (load → features → train → evaluate)
python main.py train

# Outputs:
#   artifacts/model.pkl       — trained model artifact
#   artifacts/metrics.json    — evaluation results
```

To switch model type, edit `config.yaml`:
```yaml
model:
  type: gradient_boosting  # logistic_regression | gradient_boosting | random_forest
```

---

## Results (Baseline)

| Model | ROC-AUC | F1 (minority class) | F1 macro |
|---|---|---|---|
| Logistic Regression ✓ | 0.8935 | 0.4929 | 0.6858 |
| Gradient Boosting | 0.8992 | 0.4516 | 0.6947 |

**Selected model**: Logistic Regression — marginally lower ROC-AUC but materially better minority-class F1, faster training, and interpretable for business stakeholders.

> Note: Accuracy is not reported. With 88.4% majority class, it is misleading. ROC-AUC and F1 on the minority class are the relevant metrics.

---

## Project Structure

```
bank-marketing-mlops-azure/
│
├── config.yaml               # Single source of truth for all configuration
├── main.py                   # Pipeline entry point — `python main.py train`
├── Dockerfile.train          # Training container — runs full pipeline
├── Dockerfile.infer          # Inference container — FastAPI + Uvicorn
├── kind-config.yaml          # KinD cluster config for local K8s testing
├── requirements.txt          # Training dependencies (pinned)
├── requirements-infer.txt    # Inference dependencies (pinned, minimal)
├── requirements-local.txt    # Local/CI dependencies (includes pytest)
│
├── src/
│   ├── config.py             # YAML config loader
│   ├── data.py               # Data loading (config-driven, path-safe)
│   ├── features.py           # Cleaning, feature engineering, preprocessing pipeline
│   ├── train.py              # Model training + artifact saving
│   ├── evaluate.py           # Evaluation metrics + metrics.json output
│   ├── storage.py            # Storage abstraction (local filesystem / Azure Blob)
│   └── api/
│       └── app.py            # FastAPI serving layer (see API section below)
│
├── tests/                    # pytest test suite
│
├── notebooks/                # Jupyter notebooks (EDA, setup, Docker, K8s)
│
├── artifacts/
│   ├── model.pkl             # Trained sklearn Pipeline (preprocessor + classifier)
│   └── metrics.json          # Evaluation results
│
├── data/
│   └── raw/                  # Raw CSV data (excluded from git via .gitignore)
│
├── k8s/                      # Kubernetes manifests (deployment, service, quota, secret)
│
└── .azure/                   # Azure DevOps CI/CD pipeline definitions
    ├── pr-validation.yml
    ├── azure-pipelines.yml
    └── retrain.yml
```

---

## Configuration

All pipeline behaviour is driven by `config.yaml`. No hardcoded values exist in the codebase.

```yaml
data:
  raw_path: data/raw/bank_marketing_data.csv  # Path relative to repo root
  separator: ";"
  index_col: 0

features:
  age_cap: 100                              # Cap implausible ages (EDA finding)
  log_transform_cols: [duration, campaign]  # Right-skewed positives
  signed_log_cols: [balance]                # Right-skewed with negative values
  drop_cols: [post_campaign_action]         # Post-hoc variable — data leakage risk

model:
  target_column: target
  type: logistic_regression
  test_size: 0.2
  random_state: 42

artifacts:
  model_path: artifacts/model.pkl
  metrics_path: artifacts/metrics.json
```

### Environment variables

Runtime behaviour is controlled by environment variables. Local dev uses defaults; cloud values are set via the `bank-marketing-vars` variable group in Azure DevOps (pipelines) and K8s secrets / `deployment.yaml` (inference pods).

| Variable | Default | Scope | Description |
|---|---|---|---|
| `STORAGE_BACKEND` | `local` | Local + inference pod | `local` or `azure_blob`. CI training always uses `local`; inference pod sets `azure_blob` via `deployment.yaml` |
| `AZURE_STORAGE_CONNECTION_STRING` | _(unset)_ | Local dev only | Blob auth — use when testing blob I/O locally |
| `AZURE_STORAGE_ACCOUNT_NAME` | _(unset)_ | AKS inference pod | Blob auth via AKS managed identity — pulled from K8s secret in `deployment.yaml` |
| `AZURE_STORAGE_CONTAINER` | _(unset)_ | Local + inference pod | Blob container name — required when `STORAGE_BACKEND=azure_blob` |
| `MODEL_BLOB_PREFIX` | _(unset)_ | Inference pod | `staging` or `production` — determines which blob path the pod loads `model.pkl` from |
| `MODEL_PATH` | from `config.yaml` | Local dev only | Override model artifact path locally; not used in cloud (use `MODEL_BLOB_PREFIX` instead) |

See [docs/local-development.md](docs/local-development.md#5-environment-variables) for full examples.

---

## Source Modules

### `src/data.py`
Loads raw CSV data using config-driven path resolution. The `raw_path` is resolved relative to the config file's location, making it callable from any working directory (repo root, `notebooks/`, Docker container, etc).

Key function: `load_data(config_path) -> pd.DataFrame`

### `src/features.py`
Applies EDA-driven cleaning and builds the scikit-learn preprocessing pipeline. All decisions here trace back to findings in `notebooks/01_eda.ipynb`.

Key cleaning steps:
- Drops `post_campaign_action` (post-hoc variable, data leakage risk)
- Caps `age > 100` (4 data entry errors found in EDA)
- Creates `contacted_before` binary flag from `pdays == -1` sentinel
- Applies `log1p` to right-skewed columns (`duration`, `campaign`)
- Applies sign-preserving log to `balance` (can be negative)

Key functions: `clean_data()`, `split_data()`, `build_preprocessor()`

### `src/train.py`
Instantiates the configured model and fits a full `sklearn.pipeline.Pipeline` (preprocessor + classifier together). The saved artifact is self-contained — loading it at inference requires no separate preprocessing code.

Key functions: `get_model()`, `train()`, `save_model()`

### `src/evaluate.py`
Evaluates the trained pipeline on the held-out test set and saves `metrics.json`. Also exposes `load_model()` for re-evaluation without retraining.

Key functions: `evaluate()`, `save_metrics()`, `load_model()`

---

## Architecture

```
GitHub (source control)
    │
    ▼
Azure DevOps Pipelines (CI/CD)
    │
    ├── CI: install → test → train → upload model to Blob Storage
    │
    ├── CD: build inference image → push to ACR → deploy to AKS
    │
    └── Model promotion: Blob copy builds/<id> → staging/ or production/
                                │
                                ▼
                    AKS Pod: FastAPI service
                        │  loads model.pkl from Azure Blob Storage
                        │  (MODEL_BLOB_PREFIX=staging|production)
                        │  POST /predict → {"prediction": 0, "probability": 0.18, "label": "no"}
                        │
                        ▼
                    Azure Monitor / Application Insights
                        (latency, errors, prediction distribution)
```

---

## Reproducibility

Full reproducibility is enforced by:
- **Fixed random seed** in `config.yaml` (`random_state: 42`)
- **Pinned dependencies** in `requirements.txt`
- **Config-driven pipeline** — identical config always produces identical artifacts
- **Stratified split** — class distribution preserved across train/test sets
- **Single entry point** — `python main.py train` is the only command needed

---

## API (FastAPI)

The model is served via a FastAPI application in `src/api/`.

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

```
POST /predict  (requires X-API-Key header when API_KEY is set)
{
  "age": 35,
  "job": "management",
  "marital": "married",
  ...
}
→ {"prediction": 0, "probability": 0.18, "label": "no"}

GET /health  → {"status": "healthy"}
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| ML | scikit-learn |
| Serving | FastAPI + Uvicorn |
| Containerisation | Docker |
| Registry | Azure Container Registry (ACR) |
| Model Storage | Azure Blob Storage (prefix-based promotion) |
| Orchestration | Azure Kubernetes Service (AKS) |
| CI/CD | Azure DevOps Pipelines |
| Monitoring | Azure Monitor + Application Insights |

---

## Documentation

Detailed system design and operational documentation:

| Document | Description |
|---|---|
| [System Architecture](docs/architecture.md) | High-level architecture, component breakdown, data flow diagrams |
| [Git Workflow](docs/git-workflow.md) | GitFlow branching strategy, CI triggers, merge and release flow |
| [CI/CD Pipeline](docs/ci-cd-pipeline.md) | Build, test, containerise, and deploy pipeline stages |
| [Deployment Architecture](docs/deployment.md) | AKS structure, Kubernetes manifests, API exposure, container lifecycle |
| [MLOps Lifecycle](docs/mlops-lifecycle.md) | Training → deployment → monitoring → retraining lifecycle |
| [Design Tradeoffs](docs/design-tradeoffs.md) | Architectural decisions with tradeoff analysis |
| [Future Enhancements](docs/future-enhancements.md) | Planned improvements and upgrade paths |
| [Local Development](docs/local-development.md) | Dev container setup, local testing, KinD cluster |
| [Operationalisation](docs/operationalisation.md) | Azure infrastructure provisioning, ADO setup, deployment validation |
