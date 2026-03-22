# System Architecture

End-to-end infrastructure and system design for the Bank Marketing MLOps project — covering the development environment, Azure resources, CI/CD pipelines, container and Kubernetes architecture, and production observability.

---

## Table of Contents

1. [Solution Overview](#solution-overview)
2. [Development Environment](#development-environment)
3. [Azure Infrastructure](#azure-infrastructure)
4. [Source Control & Branch Strategy](#source-control--branch-strategy)
5. [CI/CD Pipeline Architecture](#cicd-pipeline-architecture)
6. [Container Architecture](#container-architecture)
7. [Kubernetes Architecture](#kubernetes-architecture)
8. [Observability](#observability)
9. [ML Data Flow](#ml-data-flow)
10. [Key Design Decisions](#key-design-decisions)
11. [Key References](#key-references)

---

## Solution Overview

```mermaid
flowchart LR
    subgraph Dev["Development"]
        DC["Dev Container<br/>Python 3.12 · Docker · Azure CLI"]
    end

    subgraph Source["Source Control"]
        GH["GitHub Repository<br/>Branch protection on dev + main"]
    end

    subgraph CI_CD["CI/CD — Azure DevOps"]
        P1["Pipeline 1<br/>pr-validation"]
        P2["Pipeline 2<br/>ci-cd"]
        ENV["Environment<br/>production (approval gate)"]
    end

    subgraph Azure["Azure Resources"]
        ACR["Azure Container Registry<br/>bankmarketingacr (Basic)"]
        subgraph AKS["AKS Cluster — bank-marketing-aks"]
            subgraph NS_PROD["Namespace: bank-marketing (production)"]
                POD_PROD["2 replicas · FastAPI + model.pkl"]
                SVC_PROD["Service: LoadBalancer"]
            end
            subgraph NS_DEV["Namespace: bank-marketing-dev (staging)"]
                POD_DEV["1 replica · FastAPI + model.pkl"]
                SVC_DEV["Service: ClusterIP (internal)"]
            end
        end
        MON["Azure Monitor"]
        AI["Application Insights"]
    end

    DC -->|"commit + push"| GH
    GH -->|"PR webhook"| P1
    GH -->|"push webhook"| P2
    P2 -->|"main: sha+latest / dev: dev-sha"| ACR
    P2 -->|"main → bank-marketing / dev → bank-marketing-dev"| AKS
    ENV -.->|"approval gate"| P2
    ACR -->|"image pull (AcrPull)"| POD_PROD
    ACR -->|"image pull (AcrPull)"| POD_DEV
    POD_PROD --> SVC_PROD
    POD_DEV --> SVC_DEV
    POD_PROD -->|"metrics + logs"| MON
    POD_PROD -->|"traces + errors"| AI
```

### Component Summary

| Layer | Component | Purpose |
|---|---|---|
| Development | Dev Container | Reproducible local environment (Python 3.12, Docker, Azure CLI) |
| Source Control | GitHub | Code, config, pipeline definitions, branch protection |
| CI/CD | Azure DevOps Pipelines | Two-pipeline architecture — PR validation + push-triggered CI/CD |
| Registry | Azure Container Registry | Private Docker image hosting (Basic SKU) |
| Runtime | Azure Kubernetes Service | Managed Kubernetes cluster — two namespaces: `bank-marketing` (production) and `bank-marketing-dev` (staging) |
| Observability | Azure Monitor + App Insights | Metrics, logs, traces, and alerting |

---

## Development Environment

Local development runs inside a VS Code Dev Container. All dependencies, tooling, and CLI access are pre-configured — no host machine setup beyond Docker Desktop and VS Code.

| Concern | Configuration |
|---|---|
| Base image | `mcr.microsoft.com/devcontainers/python:3.12-bookworm` |
| Docker access | Docker-outside-of-Docker feature (uses host Docker daemon) |
| Azure CLI | Pre-installed via Dev Container feature |
| Python deps | Installed automatically via `postCreateCommand: pip install -r requirements.txt` |
| ML pipeline | `python main.py train` / `python main.py predict` |
| Tests | `python -m pytest tests/ -v --tb=short` |
| Container build | `docker build` from inside the Dev Container |
| K8s validation | `kubeconform -strict k8s/` (manual install) |

> See [docs/local-development.md](local-development.md) for detailed commands covering the full local development workflow.

---

## Azure Infrastructure

All Azure resources are provisioned via Azure CLI (console-first approach). Migration to Terraform is tracked as a future consideration.

```mermaid
flowchart TD
    SUB["Azure Subscription"] --> RG["Resource Group<br/>rg-bank-marketing<br/>Region: South Africa North"]

    RG --> ACR["Azure Container Registry<br/>bankmarketingacr<br/>SKU: Basic"]
    RG --> AKS["Azure Kubernetes Service<br/>bank-marketing-aks<br/>2 nodes · Standard_B2s"]
    RG --> MON["Azure Monitor<br/>(AKS monitoring addon)"]
    RG --> AI["Application Insights<br/>bank-marketing-insights"]

    ACR ---|"AcrPull role (--attach-acr)"| AKS
```

### Resource Inventory

| Resource | Name | SKU / Size | Purpose |
|---|---|---|---|
| Resource Group | `rg-bank-marketing` | — | Logical grouping for all project resources |
| Container Registry | `bankmarketingacr` | Basic | Private Docker image hosting |
| Kubernetes Service | `bank-marketing-aks` | 2× Standard_B2s nodes | Managed cluster running the prediction API |
| Monitor | *(AKS addon)* | — | Cluster-level metrics, logs, and alerts |
| Application Insights | `bank-marketing-insights` | — | Application-level traces, errors, and performance |

### ACR–AKS Integration

AKS is created with `--attach-acr bankmarketingacr`, which grants the AKS managed identity the `AcrPull` role on the registry. This eliminates the need for `imagePullSecrets` in Kubernetes manifests.

> See [docs/todos.md § 2](todos.md#2-azure-infrastructure-setup-console) for the full provisioning checklist.

---

## Source Control & Branch Strategy

Source code lives on **GitHub**. Azure DevOps connects to the GitHub repo via a service connection — no code is stored in Azure Repos Git.

### Branch Model

```mermaid
gitGraph
    commit id: "init"
    branch dev
    checkout dev
    commit id: "pipeline-v1"
    branch feature/api
    checkout feature/api
    commit id: "fastapi-app"
    checkout dev
    merge feature/api id: "merge-api"
    branch release/1.0
    checkout release/1.0
    commit id: "stabilise"
    checkout main
    merge release/1.0 id: "v1.0.0" tag: "v1.0.0"
    checkout dev
    merge release/1.0 id: "back-merge"
```

| Branch | Purpose | Protected | CI/CD Trigger |
|---|---|---|---|
| `main` | Production-ready code | Yes (GitHub branch protection) | Push → Pipeline 2 (`CD_Main` — production deploy to `bank-marketing`) |
| `dev` | Integration branch | Yes (GitHub branch protection) | Push → Pipeline 2 (`CD_Dev` — staging deploy to `bank-marketing-dev`) |
| `feature/*` | Individual work items | No | PR → Pipeline 1 (validation) |
| `release/*` | Release stabilisation | No | PR → Pipeline 1 (validation) |

### Branch Protection (GitHub)

Both `dev` and `main` have GitHub branch protection rules:

- **Require status checks**: The `pr-validation` pipeline must pass before merge
- **Require PR reviews**: At least 1 approval required
- **Dismiss stale approvals**: Re-review required after new commits
- **Require conversation resolution**: All comments must be resolved

The `pr:` YAML keyword in `pr-validation.yml` controls which target branches trigger the validation pipeline. This works because the repo is on GitHub — Azure Repos Git does not support `pr:` triggers.

> See [docs/git-workflow.md](git-workflow.md) for the full branching strategy and merge conventions.

---

## CI/CD Pipeline Architecture

Two separate Azure DevOps pipelines enforce consistent PR validation while keeping deployment logic isolated.

```mermaid
flowchart TD
    subgraph Triggers["Trigger Events"]
        PR_EV["PR opened / updated<br/>(targeting dev or main)"]
        PUSH_DEV["Push to dev<br/>(merge)"]
        PUSH_MAIN["Push to main<br/>(merge)"]
    end

    subgraph P1["Pipeline 1: pr-validation.yml"]
        VAL["Install → pytest → kubeconform<br/>→ Docker build → smoke test"]
    end

    subgraph P2_DEV["Pipeline 2 (dev path)"]
        CI_D["CI: Install → pytest → kubeconform"]
        CD_D["CD_Dev: Docker build + push (dev-sha)<br/>→ kubectl apply (bank-marketing-dev)<br/>→ in-cluster smoke test"]
        CI_D --> CD_D
    end

    subgraph P2_MAIN["Pipeline 2 (main path)"]
        CI_M["CI: Install → pytest → kubeconform"]
        CD_M["CD_Main: Docker build + push → ACR<br/>→ kubectl apply → AKS<br/>→ live smoke test"]
        CI_M --> CD_M
    end

    PR_EV --> P1
    PUSH_DEV --> P2_DEV
    PUSH_MAIN --> P2_MAIN
```

### Pipeline 1 — PR Validation (`pr-validation.yml`)

Triggered by PRs targeting `dev` or `main` via the `pr:` YAML keyword. Runs identical validation for all PRs — no conditions or branching logic.

| Step | What it catches |
|---|---|
| `pytest` | Logic errors, API contract changes, config mistakes |
| `kubeconform` | K8s manifest schema errors, invalid resource specs |
| Docker build | Dockerfile errors, missing dependencies at image build time |
| Container smoke test | Model loading failures, startup crashes, port issues |

### Pipeline 2 — CI/CD (`azure-pipelines.yml`)

Triggered by pushes (merges) to `dev` and `main`. Runs a shared CI stage followed by a branch-conditional CD stage:

| Target Branch | CD Stage | ACR Push | AKS Deploy | Approval Gate |
|---|---|---|---|---|
| `dev` | `CD_Dev` (staging) | Yes (`dev-<sha>`) | `kubectl apply -n bank-marketing-dev` | No |
| `main` | `CD_Main` (production) | Yes | `kubectl apply` | Yes (`production` environment) |

### Why Two Pipelines?

| Concern | Two pipelines (this project) |
|---|---|
| PR validation consistency | Guaranteed identical — Pipeline 1 has no conditions |
| CD logic isolation | CD logic only exists in Pipeline 2 |
| Failure diagnosis | Pipeline 1 = validation; Pipeline 2 = build/deploy |

### Service Connections

Azure DevOps authenticates with external services via three service connections:

| Connection | Type | Purpose |
|---|---|---|
| `github-connection` | GitHub | Access repo, receive webhook events |
| `azure-sub-connection` | Azure Resource Manager | AKS access, general Azure operations |
| `acr-connection` | Docker Registry (ACR) | Push/pull container images |

### Environment & Approval Gate

The `CD_Main` stage references `environment: 'production'` in Azure DevOps. This environment is configured with:

- **Approval check** — at least one approver must approve before the production deploy stage runs
- **Exclusive lock** (optional) — prevents concurrent deployments to production

> See [docs/ci-cd-pipeline.md](ci-cd-pipeline.md) for full pipeline YAML definitions and stage-by-stage breakdown.

---

## Container Architecture

The FastAPI application is packaged as a Docker image containing the application code, dependencies, and the trained model artifact.

### Image Contents

| Layer | Contents |
|---|---|
| Base | `python:3.12-slim` |
| Dependencies | `requirements.txt` installed via pip |
| Application | `src/` + `config.yaml` |
| Model artifact | `artifacts/model.pkl` |
| Entrypoint | `uvicorn src.api.app:app --host 0.0.0.0 --port 8000` |

### Image Tagging Strategy

| Tag | When Applied | Purpose |
|---|---|---|
| `<git-commit-sha>` | ACR push on main merges | Immutable identifier for production traceability |
| `latest` | ACR push on main merges | Convenience tag for rolling production deployments |
| `dev-<git-commit-sha>` | ACR push on dev merges | Staging image — maps the exact dev commit deployed to `bank-marketing-dev` |

### Build Contexts

| Context | Where | Push to ACR? |
|---|---|---|
| Local development | Dev Container (`docker build`) | No |
| PR validation | Pipeline 1 (Microsoft-hosted agent) | No |
| Dev merge | Pipeline 2 / `CD_Dev` | Yes (`dev-<sha>`) |
| Main merge | Pipeline 2 / `CD_Main` | Yes |

---

## Kubernetes Architecture

### Cluster Layout

```mermaid
flowchart TD
    subgraph AKS["AKS Cluster — bank-marketing-aks"]
        subgraph NS_PROD["Namespace: bank-marketing (production)"]
            DEP_PROD["Deployment: bank-marketing-api<br/>2 replicas · FastAPI + model.pkl"]
            SVC_PROD["Service: bank-marketing-api<br/>Type: LoadBalancer · Port 80 → 8000"]
        end
        subgraph NS_DEV["Namespace: bank-marketing-dev (staging)"]
            DEP_DEV["Deployment: bank-marketing-api<br/>1 replica · FastAPI + model.pkl"]
            SVC_DEV["Service: bank-marketing-api<br/>Type: ClusterIP · Port 8000 (internal)"]
            RQ["ResourceQuota: 1 CPU max · 512Mi max"]
        end
    end

    ACR["ACR · bankmarketingacr"]
    LB["Azure Load Balancer · External IP"]
    CLIENT["Client / Upstream Service"]
    CICD["CD_Dev (Pipeline 2)"]

    ACR -->|"sha + latest (AcrPull)"| DEP_PROD
    ACR -->|"dev-sha (AcrPull)"| DEP_DEV
    DEP_PROD --> SVC_PROD
    SVC_PROD --> LB
    CLIENT -->|"POST /predict"| LB
    LB --> DEP_PROD
    CICD -->|"smoke test (kubectl exec)"| SVC_DEV
```

### Resource Sizing

| Resource | Spec | Rationale |
|---|---|---|
| Node pool | 2× Standard_B2s | Cost-effective for lightweight inference workloads |
| Replicas (`bank-marketing`) | 2 | Basic availability — zero-downtime during rolling updates |
| Replicas (`bank-marketing-dev`) | 1 | Single replica sufficient for staging smoke tests |
| CPU request / limit | 250m / 500m | Logistic regression inference is lightweight |
| Memory request / limit | 256Mi / 512Mi | `model.pkl` is small (< 10MB) |
| Dev namespace `ResourceQuota` | 1 CPU, 512Mi | Prevents the staging workload from competing with production on shared nodes |

### Health Probes

| Probe | Endpoint | Timing | Behaviour |
|---|---|---|---|
| Readiness | `GET /health` | initial: 5s, period: 10s | Pod only receives traffic after probe passes |
| Liveness | `GET /health` | initial: 10s, period: 15s | Pod restarted after 3 consecutive failures |

### API Endpoints

| Method | Path | Purpose | Used By |
|---|---|---|---|
| `POST` | `/predict` | Score a single customer record | Upstream services, batch callers |
| `GET` | `/health` | Liveness/readiness probe | Kubernetes, CI smoke tests |
| `GET` | `/docs` | Auto-generated OpenAPI documentation | Developers (FastAPI built-in) |

> See [docs/deployment.md](deployment.md) for full Kubernetes manifest YAML and the container lifecycle.

---

## Observability

### Azure Monitor (AKS Addon)

Enabled via `az aks enable-addons --addons monitoring`. Provides:

- Pod-level CPU and memory utilisation
- Node health and cluster-level metrics
- Container log aggregation
- Alerting rules for resource thresholds

### Application Insights

Provisioned as a standalone resource (`bank-marketing-insights`). Provides:

- Request latency and throughput per endpoint
- Error rates and HTTP status code distribution
- Prediction distribution drift (logged per-request)
- End-to-end transaction traces

---

## ML Data Flow

```mermaid
flowchart TD
    subgraph Training["Training Pipeline (offline)"]
        RAW["Raw CSV Data"] --> CLEAN["clean_data()"]
        CLEAN --> SPLIT["train/test split"]
        SPLIT --> PREPROC["build_preprocessor()"]
        PREPROC --> TRAIN["train() — fit Pipeline"]
        TRAIN --> ARTIFACT["artifacts/model.pkl"]
        TRAIN --> EVAL["evaluate()"]
        EVAL --> METRICS["artifacts/metrics.json"]
    end

    subgraph Serving["Serving Pipeline (online)"]
        REQ["POST /predict JSON"] --> CLEAN2["clean_data()"]
        CLEAN2 --> PREDICT["pipeline.predict()"]
        PREDICT --> RESP["JSON Response"]
    end

    ARTIFACT -.->|"baked into Docker image"| PREDICT
```

### Training Flow (Offline)

1. `main.py train` loads `config.yaml` and raw CSV data
2. `clean_data()` applies EDA-driven transformations (leakage column removal, age capping, log transforms, target encoding)
3. Stratified train/test split preserves class distribution
4. `build_preprocessor()` creates an unfitted `ColumnTransformer` (impute → scale for numerics, one-hot for categoricals)
5. `train()` wraps preprocessor + classifier into a single `sklearn.Pipeline` and fits on training data
6. The fitted pipeline is serialised to `artifacts/model.pkl` — self-contained, no external preprocessing needed
7. `evaluate()` scores the held-out test set and writes metrics to `artifacts/metrics.json`

### Serving Flow (Online)

1. FastAPI application loads `model.pkl` once at startup (via lifespan handler)
2. Incoming `POST /predict` requests are validated by Pydantic
3. The request is converted to a single-row DataFrame
4. `clean_data()` applies the same feature engineering as training
5. `pipeline.predict()` and `pipeline.predict_proba()` generate the response
6. JSON response returns `prediction`, `probability`, and `label`

> See [docs/mlops-lifecycle.md](mlops-lifecycle.md) for the full inner loop → outer loop → feedback loop lifecycle.

---

## Key Design Decisions

### Infrastructure

| Decision | Rationale |
|---|---|
| GitHub + Azure DevOps Pipelines | Source control on GitHub (existing repo); ADO provides native Azure service connections and `pr:` YAML triggers for GitHub repos |
| Two-pipeline CI/CD | Isolates PR validation from deployment logic — cleaner failure diagnosis and branch policy configuration |
| Console-first provisioning | Azure CLI for initial setup; Terraform planned as a future enhancement after the baseline is validated |
| ACR Basic SKU | Sufficient for a single-service project; upgradeable if geo-replication or content trust is needed |
| AKS with `--attach-acr` | Grants `AcrPull` via managed identity — eliminates `imagePullSecrets` and manual credential rotation |
| 2× Standard_B2s nodes | Cost-effective burstable VMs suited to lightweight sklearn inference |
| Namespace-based environment isolation | Two namespaces (`bank-marketing` + `bank-marketing-dev`) within the same AKS cluster — provides a real staging environment without provisioning a second cluster. Follows [Microsoft's AKS isolation guidance](https://learn.microsoft.com/en-us/azure/aks/operator-best-practices-cluster-isolation): *"Separate teams and projects using logical isolation. Minimize the number of physical AKS clusters you deploy."* |
| `production` environment with approval gate | Prevents unreviewed code from reaching production even if branch protection is misconfigured |

### Application

| Decision | Rationale |
|---|---|
| Single sklearn Pipeline artifact | Eliminates preprocessing/model version mismatch at inference time |
| Config-driven pipeline | `config.yaml` is the single source of truth — no hardcoded values |
| FastAPI over Flask | Async-capable, built-in Pydantic validation, auto-generated OpenAPI docs |
| `/health` endpoint | Required for Kubernetes liveness/readiness probes |
| Logistic Regression as default | Interpretable, fast to train, better minority-class F1 than gradient boosting for this dataset |
| Model baked into Docker image | Self-contained deployable unit — no external model store required for this project's scope |

---

## Key References

> Reference numbers correspond to [REFERENCES.md](../REFERENCES.md).

### MLOps Architecture

- **[8]** Microsoft. [Machine learning operations (MLOps v2)](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/machine-learning-operations-v2). Canonical Azure MLOps reference defining the inner loop → outer loop lifecycle — the architectural pattern this project implements.
- **[22]** Microsoft/Azure. [MLOps v2 — Classical ML Architecture Diagram](https://github.com/Azure/mlops-v2/blob/main/documentation/architecture/media/AzureML_CML_Architecture.png). Visual benchmark for the AzureML MLOps v2 classical ML architecture — the source model for the GitHub → ADO → ACR → AKS topology.

### Azure Infrastructure

- **[34]** Microsoft. [Azure Kubernetes Service (AKS) documentation](https://learn.microsoft.com/en-us/azure/aks/). Core reference for AKS cluster creation, networking, scaling, and monitoring.
- **[35]** Microsoft. [Azure Container Registry documentation](https://learn.microsoft.com/en-us/azure/container-registry/). ACR setup, authentication, and image management.
- **[36]** Microsoft. [Authenticate with Azure Container Registry from AKS](https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration). Documents the `--attach-acr` integration method and `AcrPull` role assignment used in this project.
- **[37]** Microsoft. [Azure Monitor container insights overview](https://learn.microsoft.com/en-us/azure/azure-monitor/containers/container-insights-overview). AKS monitoring addon configuration and the metrics/logs it provides.

### CI/CD & Deployment

- **[25]** Microsoft. [Build GitHub repositories](https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/github?view=azure-devops&tabs=yaml). Comprehensive reference for connecting GitHub repos to Azure Pipelines — covers service connections, webhook installation, and `pr:` / `trigger:` YAML syntax.
- **[12]** Microsoft. [Build a CI/CD pipeline for microservices on Kubernetes](https://learn.microsoft.com/en-us/azure/architecture/microservices/ci-cd-kubernetes). Architecture guide covering deployment, environment isolation, and the validation builds pattern that informed the two-pipeline design.
- **[17]** Microsoft. [Online Endpoints — Managed vs Kubernetes Online Endpoints](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#managed-online-endpoints-vs-kubernetes-online-endpoints). Reference for the decision to use direct AKS deployment over AzureML managed online endpoints.
