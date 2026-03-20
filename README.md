# Bank Marketing MLOps — Nedbank ML Engineering Assessment

A production-grade ML system for predicting bank term deposit subscriptions.
Built to demonstrate MLOps engineering practices: reproducible pipelines, containerised deployment, CI/CD via Azure DevOps, and serving on AKS.

> **Problem statement**: Predict whether a customer will subscribe to a term deposit (`target = yes/no`) based on demographic and campaign interaction data.

---

## Quick Start

```bash
# 1. Clone and install dependencies
pip install -r requirements.txt

# 2. Run the full training pipeline (load → features → train → evaluate)
python main.py

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
├── main.py                   # Pipeline entry point — run this to train
├── requirements.txt          # Pinned dependencies
│
├── src/
│   ├── data.py               # Data loading (config-driven, path-safe)
│   ├── features.py           # Cleaning, feature engineering, preprocessing pipeline
│   ├── train.py              # Model training + artifact saving
│   ├── evaluate.py           # Evaluation metrics + metrics.json output
│   └── api/                  # FastAPI serving layer (see API section below)
│
├── notebooks/
│   └── 01_eda.ipynb          # Exploratory data analysis (observation only)
│
├── artifacts/
│   ├── model.pkl             # Trained sklearn Pipeline (preprocessor + classifier)
│   └── metrics.json          # Evaluation results (tracked in git)
│
├── data/
│   └── raw/                  # Raw CSV data (excluded from git via .gitignore)
│
└── .github/
    ├── agents/               # VS Code Copilot agent definitions
    └── pipelines/            # Azure DevOps CI/CD pipeline definitions (coming)
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
    ├── CI: install → test → docker build → push to ACR
    │
    └── CD: pull from ACR → deploy to AKS → smoke test
                                │
                                ▼
                    AKS Pod: FastAPI service
                        │  loads artifacts/model.pkl
                        │  POST /predict → {"subscription_probability": 0.73}
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
- **Single entry point** — `python main.py` is the only command needed

---

## API (FastAPI — coming next)

The model is served via a FastAPI application in `src/api/`.

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

```
POST /predict
{
  "age": 35,
  "job": "admin.",
  "marital": "married",
  ...
}
→ {"subscribed": 0, "probability": 0.18}

GET /health  → {"status": "ok", "model": "logistic_regression"}
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
| Orchestration | Azure Kubernetes Service (AKS) |
| CI/CD | Azure DevOps Pipelines |
| Monitoring | Azure Monitor + Application Insights |
