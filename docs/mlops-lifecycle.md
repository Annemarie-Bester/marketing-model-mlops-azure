# MLOps Lifecycle

Training, deployment, monitoring, and retraining lifecycle for the Bank Marketing prediction model.

---

## Lifecycle Overview

```mermaid
flowchart TD
    subgraph Inner["Inner Loop — Model Development"]
        DATA["Data Ingestion<br/>data/raw/bank_marketing_data.csv"]
        EDA["EDA<br/>notebooks/01_eda.ipynb"]
        FEAT["Feature Engineering<br/>src/features.py"]
        TRAIN["Training<br/>src/train.py"]
        EVAL["Evaluation<br/>src/evaluate.py"]
        ARTIFACT["Artifact<br/>artifacts/model.pkl<br/>artifacts/metrics.json"]

        DATA --> EDA --> FEAT --> TRAIN --> EVAL --> ARTIFACT
    end

    subgraph Outer["Outer Loop — Model Deployment"]
        CI["CI: test + build + push to ACR"]
        CD["CD: deploy to AKS"]
        SERVE["Serving: FastAPI<br/>POST /predict"]
        MONITOR["Monitoring<br/>Azure Monitor + App Insights"]
    end

    subgraph Feedback["Feedback Loop"]
        DRIFT["Drift Detection<br/>prediction distribution shift"]
        RETRAIN["Retrain Decision<br/>update data → re-run pipeline"]
    end

    ARTIFACT --> CI --> CD --> SERVE --> MONITOR
    MONITOR --> DRIFT
    DRIFT -->|"drift detected"| RETRAIN
    RETRAIN -->|"new data / config"| DATA
```

---

## Inner Loop — Model Development

The inner loop is where data scientists and ML engineers iterate on the model.

### Pipeline Stages

| Stage | Module | Input | Output |
|---|---|---|---|
| Load data | `src/data.py` | `config.yaml` → `data/raw/*.csv` | Raw DataFrame |
| Clean & engineer | `src/features.py` | Raw DataFrame + config | Cleaned DataFrame |
| Split | `src/features.py` | Cleaned DataFrame | Train/test sets (stratified) |
| Build preprocessor | `src/features.py` | Training features | Unfitted `ColumnTransformer` |
| Train | `src/train.py` | Train set + preprocessor + config | Fitted `sklearn.Pipeline` |
| Evaluate | `src/evaluate.py` | Fitted pipeline + test set | Metrics dict |
| Save | `src/train.py` + `src/evaluate.py` | Pipeline + metrics | `model.pkl` + `metrics.json` |

### Execution

```bash
python main.py train
```

All behaviour is controlled by `config.yaml`. Changing the model type, test size, or feature configuration requires only a config change — no code modification.

---

## Model Versioning

This project uses a simple, Git-based versioning approach appropriate for a case study scope:

```mermaid
flowchart LR
    subgraph Versioning["Model Versioning Strategy"]
        GIT["Git commit SHA<br/>= model version"]
        PKL["artifacts/model.pkl<br/>committed to repo"]
        MET["artifacts/metrics.json<br/>committed to repo"]
        TAG["Docker image tag<br/>= Git SHA"]
    end

    GIT --> PKL
    GIT --> MET
    GIT --> TAG
```

| Approach | How |
|---|---|
| **Model identity** | Tied to Git commit SHA — each commit that changes `model.pkl` is a new model version |
| **Metrics tracking** | `artifacts/metrics.json` committed alongside the model — metrics and model always in sync |
| **Container traceability** | Docker images tagged with commit SHA — the running container maps back to exact source + model |
| **Reproducibility** | Fixed random seed + pinned dependencies + config-driven pipeline = deterministic output |

### Why not MLflow / Model Registry?

For this case study, Git-based versioning is sufficient and avoids introducing infrastructure complexity. In a production system at scale, a model registry (MLflow, Azure ML Model Registry) would provide:

- Centralised model catalogue with metadata
- Stage transitions (staging → production)
- A/B deployment support
- Automated lineage tracking

This is a deliberate simplification — the architecture supports upgrading to a registry without structural changes.

---

## Outer Loop — Model Deployment

Once a model is trained and committed, the outer loop deploys it to production.

```mermaid
flowchart LR
    COMMIT["Git commit<br/>(model.pkl + metrics.json)"]
    PR["PR → main"]
    CI["CI: tests pass"]
    BUILD["Docker build<br/>image includes model.pkl"]
    ACR["Push to ACR"]
    AKS["Deploy to AKS"]
    LIVE["Model serving<br/>via FastAPI"]

    COMMIT --> PR --> CI --> BUILD --> ACR --> AKS --> LIVE
```

### Deployment Trigger

A model is deployed when:

1. `model.pkl` is updated in the repository
2. Changes are merged to `main` via a reviewed PR
3. CI validates tests pass with the new artifact
4. CD builds a new Docker image (containing the updated model) and deploys to AKS

Human review at the PR stage acts as the approval gate for model promotion.

---

## Monitoring

### What to Monitor

| Signal | Source | Purpose |
|---|---|---|
| Request latency | Application Insights | Detect serving degradation |
| Error rate | Application Insights | Catch model failures (input schema changes, data issues) |
| Prediction distribution | Custom logging in `app.py` | Detect input/output drift |
| Pod health | Azure Monitor / AKS | Infrastructure availability |
| Resource usage | Azure Monitor | Capacity planning (CPU, memory) |

### Prediction Logging

The FastAPI app already logs per-request prediction details:

```python
logger.info("Prediction: %d (prob=%.4f) — %.1fms", pred, prob, latency_ms)
```

This enables:

- Tracking prediction distribution over time
- Detecting shifts in input patterns
- Measuring p99 latency

---

## Retraining Strategy

```mermaid
flowchart TD
    MONITOR["Monitor predictions<br/>+ business feedback"]
    DETECT["Detect trigger:<br/>• metric degradation<br/>• data drift<br/>• scheduled interval"]
    UPDATE["Update training data<br/>data/raw/*.csv"]
    RETRAIN["python main.py train"]
    COMPARE["Compare metrics<br/>new vs. current"]
    DECISION{Better?}
    COMMIT["Commit new model.pkl<br/>+ metrics.json"]
    DEPLOY["Merge → main → CI/CD"]
    KEEP["Keep current model"]

    MONITOR --> DETECT --> UPDATE --> RETRAIN --> COMPARE --> DECISION
    DECISION -->|"Yes"| COMMIT --> DEPLOY
    DECISION -->|"No"| KEEP
```

### Retraining Triggers

| Trigger | Description |
|---|---|
| **Metric degradation** | ROC-AUC or F1 drops below acceptable threshold on live data |
| **Data drift** | Input feature distributions shift significantly from training data |
| **Scheduled** | Periodic retraining (e.g., monthly) to incorporate new campaign data |
| **Business request** | New campaign types, product changes, or market shifts |

### Retraining Process

1. Obtain updated training data → place in `data/raw/`
2. Run `python main.py train` — produces new `model.pkl` + `metrics.json`
3. Compare new metrics against current production model
4. If improved: commit artifacts, open PR, merge to `main`
5. CI/CD automatically builds and deploys the new model

---

## MLOps Maturity Assessment

Using the Microsoft MLOps Maturity Model **[[9]](../REFERENCES.md)** — https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model:

| Level | Capability | This Project |
|---|---|---|
| 0 — No MLOps | Manual everything | -- |
| 1 — DevOps, no MLOps | CI/CD for code, manual model | -- |
| **2 — Automated Training** | **Automated pipeline, manual deploy** | **Partial** — pipeline is automated, deployment is CI/CD-driven |
| 3 — Automated Deployment | Full CI/CD for model + code | Target state — achieved with current architecture |
| 4 — Full MLOps | Automated retraining + monitoring + feedback loops | Future — requires drift detection automation |

**Current state**: Level 2–3. The training pipeline is fully automated and config-driven. Deployment is automated via CI/CD. Monitoring and automated retraining (Level 4) are designed but not yet fully automated.
