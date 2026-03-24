# CI/CD Pipeline

Three-pipeline architecture using Azure DevOps Pipelines — a dedicated PR validation pipeline, a push-triggered CI/CD pipeline with a TrainModel stage and branch-conditional deployment, and a standalone retraining pipeline.

---

## Pipeline Architecture

This project uses **three separate Azure DevOps pipelines**: PR validation (identical gates for all PRs), CI/CD (code-change-driven training + deployment), and retraining (data-driven model updates):

```mermaid
flowchart TD
    subgraph PR["Pipeline 1: pr-validation.yml"]
        direction TB
        PR_INSTALL["Install deps"]
        PR_TEST["Run pytest"]
        PR_K8S["kubeconform"]
        PR_TRAIN_BUILD["Build train image"]
        PR_TRAIN_RUN["Run training"]
        PR_INFER_BUILD["Build infer image"]
        PR_SMOKE["Container smoke\n(/health)"]

        PR_INSTALL --> PR_TEST --> PR_K8S --> PR_TRAIN_BUILD --> PR_TRAIN_RUN --> PR_INFER_BUILD --> PR_SMOKE
    end

    PR_EVENT["PR opened / updated"] --> PR
```

<table>
<tr>
<th>Pipeline 2 — Merge → <code>dev</code> (staging deployment)</th>
<th>Pipeline 2 — Merge → <code>main</code> (production deployment)</th>
</tr>
<tr><td>

```mermaid
flowchart TD
    DEV_MERGE["Merge → dev"] --> CI_DEV

    subgraph CI_DEV["CI Stage"]
        direction TB
        D_INSTALL["Install deps"]
        D_TEST["Run pytest"]
        D_K8S["kubeconform"]
        D_INSTALL --> D_TEST --> D_K8S
    end

    subgraph TRAIN_DEV["TrainModel Stage"]
        direction TB
        DT_BUILD["Build train image"]
        DT_RUN["Run training container"]
        DT_PUSH["Push train image → ACR"]
        DT_PUB["Publish model artifacts"]
        DT_BUILD --> DT_RUN --> DT_PUSH --> DT_PUB
    end

    subgraph CD_DEV["CD — dev (staging)"]
        direction TB
        DEV_DL["Download model artifacts"]
        DEV_BUILD["Build infer image\n+ push → ACR (dev-buildId)"]
        DEV_DEPLOY["kubectl apply\nbank-marketing-dev"]
        DEV_SMOKE["In-cluster smoke test\n(kubectl exec)"]
        DEV_DL --> DEV_BUILD --> DEV_DEPLOY --> DEV_SMOKE
    end

    CI_DEV --> TRAIN_DEV --> CD_DEV
```

</td><td>

```mermaid
flowchart TD
    MAIN_MERGE["Merge → main"] --> CI_MAIN

    subgraph CI_MAIN["CI Stage"]
        direction TB
        M_INSTALL["Install deps"]
        M_TEST["Run pytest"]
        M_K8S["kubeconform"]
        M_INSTALL --> M_TEST --> M_K8S
    end

    subgraph TRAIN_MAIN["TrainModel Stage"]
        direction TB
        MT_BUILD["Build train image"]
        MT_RUN["Run training container"]
        MT_PUSH["Push train image → ACR"]
        MT_PUB["Publish model artifacts"]
        MT_BUILD --> MT_RUN --> MT_PUSH --> MT_PUB
    end

    subgraph CD_MAIN["CD — main (production)"]
        direction TB
        MAIN_DL["Download model artifacts"]
        MAIN_BUILD["Build infer image\n+ push → ACR"]
        MAIN_DEPLOY["kubectl apply"]
        MAIN_SMOKE["Live smoke test"]
        MAIN_DL --> MAIN_BUILD --> MAIN_DEPLOY --> MAIN_SMOKE
    end

    CI_MAIN --> TRAIN_MAIN --> CD_MAIN
```

</td></tr>
<tr>
<td><strong>Differs:</strong> Inference image pushed as <code>dev-&lt;buildId&gt;</code> + <code>dev-latest</code>. Real deployment to <code>bank-marketing-dev</code> namespace — in-cluster smoke test, no external traffic.</td>
<td><strong>Differs:</strong> Inference image pushed as <code>&lt;buildId&gt;</code> + <code>latest</code>. Real deployment to AKS + live smoke test against external endpoint.</td>
</tr>
</table>

```mermaid
flowchart TD
    subgraph P3["Pipeline 3: retrain.yml (scheduled / manual)"]
        direction TB
        RT_DATA["Download data from Blob"]
        RT_PULL["Pull train-latest from ACR"]
        RT_RUN["Run training container"]
        RT_PUB["Publish model artifacts"]
        RV["ValidateModel:\nROC-AUC quality gate"]
        RS_BUILD["Build infer image"]
        RS_DEPLOY["Deploy to staging"]
        RS_SMOKE["Smoke test"]
        RP_APPROVE["Manual approval"]
        RP_BUILD["Build infer image"]
        RP_DEPLOY["Deploy to production"]
        RP_METRICS["Update baseline metrics"]

        RT_DATA --> RT_PULL --> RT_RUN --> RT_PUB --> RV
        RV --> RS_BUILD --> RS_DEPLOY --> RS_SMOKE
        RS_SMOKE --> RP_APPROVE --> RP_BUILD --> RP_DEPLOY --> RP_METRICS
    end

    SCHED["Weekly cron / manual / drift alert"] --> P3
```

### Why Three Pipelines?

| Concern | Single pipeline | Three pipelines (this project) |
|---|---|---|
| PR validation consistency | Requires `Build.Reason != 'PullRequest'` guards on every CD stage | Guaranteed identical — Pipeline 1 has no conditions |
| CD logic isolation | CD stages must check `Build.Reason` to avoid running on PRs | CD logic only exists in Pipelines 2 and 3 |
| Branch policy config | Complex — one YAML handles PR, dev push, and main push | Clean — Branch Policy points at Pipeline 1; `trigger:` drives Pipeline 2 |
| Failure diagnosis | Unclear whether a failure is a validation or deployment issue | Pipeline 1 = validation; Pipeline 2 = build/deploy; Pipeline 3 = retraining |
| Retraining independence | Retraining logic mixed with CI/CD | Pipeline 3 runs on schedule/manual trigger without code changes |

This follows Microsoft's [validation builds](https://learn.microsoft.com/en-us/azure/architecture/microservices/ci-cd-kubernetes#validation-builds) pattern: *"Once the feature is ready to merge into main, the developer opens a PR. This triggers another CI build that performs additional checks: build the code, run unit tests, build the runtime container image."* The validation build (Pipeline 1) is separate from the full CI/CD build (Pipeline 2).

---

## Pipeline 1: PR Validation (`pr-validation.yml`)

The PR validation pipeline runs **identical steps** for PRs targeting `dev` and PRs targeting `main`. No conditions, no branching logic — every PR is held to the same standard before merge.

### Azure Repos Git: Branch Policy, Not `pr:`

In Azure Repos Git, PR validation triggers **must be configured through branch policies**, not the `pr:` YAML keyword. The `pr:` trigger [only works with GitHub repositories](https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/azure-repos-git#pr-triggers).

To configure Pipeline 1 as a PR gate:

1. Navigate to **Project Settings → Repos → Branch Policies**
2. Select the `dev` branch → **Build Validation** → **Add build policy**
3. Select `pr-validation` as the build pipeline
4. Set **Trigger** to "Automatic" and **Policy requirement** to "Required"
5. Repeat for the `main` branch with identical settings

Both branches point at the same pipeline definition. The steps are identical.

### Pipeline Definition

> **Pipeline file:** [`.ado/pr-validation.yml`](../.ado/pr-validation.yml)

The PR validation pipeline builds **both containers** locally (no ACR push) to validate the full training → inference flow:

1. Install Python dependencies (`requirements-local.txt` — includes pytest)
2. Run `pytest`
3. Validate K8s manifests with `kubeconform`
4. Build the training image (`Dockerfile.train`)
5. Run the training container — produces `model.pkl` on the agent
6. Build the inference image (`Dockerfile.infer`) — bakes in `model.pkl`
7. Ephemeral container smoke test — `GET /health` against the inference container

### What This Validates

| Check | What it catches | Why it matters at PR stage |
|---|---|---|
| `pytest` | Logic errors, API contract changes, config mistakes | Fastest feedback loop — developer fixes before review |
| `kubeconform` | K8s manifest schema errors, invalid resource specs | Catches YAML issues before they enter the integration branch |
| Train image build + run | Dockerfile.train errors, training pipeline failures | Training failures caught before merge |
| Infer image build | Dockerfile.infer errors, missing model artifact | Build failures caught before merge, not after |
| Container smoke test | Model loading failures, startup crashes, port issues | Runtime errors caught locally, not after AKS deployment |

---

## Pipeline 2: CI/CD (`azure-pipelines.yml`)

The CI/CD pipeline is triggered by **pushes** (merges) to `dev` and `main`. It runs a shared CI stage, then a TrainModel stage (build + run training container, push to ACR, publish model artifacts), followed by a **branch-conditional CD stage** that builds the inference image with the model baked in:

- **Merge → `dev`**: Staging deployment — downloads model artifacts, builds inference image with `model.pkl` baked in, pushes to ACR, deploys to the `bank-marketing-dev` namespace, and runs an in-cluster smoke test
- **Merge → `main`**: Production deployment — downloads model artifacts, builds inference image, pushes to ACR, deploys to AKS `bank-marketing` namespace, and runs a live smoke test against the external endpoint

### CI Stage — Test & Validate

The CI stage runs on every push to both branches. It repeats the test and manifest validation steps from Pipeline 1 because the merge commit differs from the PR head commit — re-validation confirms nothing broke during the merge.

> **Pipeline file:** [`.ado/azure-pipelines.yml`](../.ado/azure-pipelines.yml)

1. Install Python dependencies (`requirements-local.txt`)
2. Run `pytest`
3. Validate K8s manifests with `kubeconform`

### TrainModel Stage — Build, Train, Push, Publish

After CI passes, the TrainModel stage builds the training container, runs training to produce `model.pkl`, pushes the training image to ACR (for reuse by the retrain pipeline), and publishes the model artifacts as a pipeline artifact for the CD stages.

1. Log in to ACR
2. Build training image (`Dockerfile.train`)
3. Run training container — mounts `data/` and `artifacts/` from the agent
4. Verify `model.pkl` and `metrics.json` exist
5. Push training image to ACR (`<buildId>` + `train-latest`)
6. Publish `artifacts/` as a pipeline artifact (`model-artifacts`)

### CD Stage — Staging Deployment (Merge → `dev`)

On merge to `dev`, the CD stage downloads the model artifacts from TrainModel, builds an inference image with `model.pkl` baked in, pushes it to ACR tagged `dev-<buildId>` + `dev-latest`, deploys to the `bank-marketing-dev` namespace, and runs an in-cluster smoke test against the internal `ClusterIP` service. The `bank-marketing` production namespace is untouched.

1. Download `model-artifacts` from the TrainModel stage
2. Stage `model.pkl` into `artifacts/` for the Docker build context
3. Build and push inference image (`Dockerfile.infer`) to ACR as `dev-<buildId>` + `dev-latest`
4. Deploy to `bank-marketing-dev` namespace via `KubernetesManifest@1`
5. In-cluster smoke test — `kubectl exec` → `GET /health`

**What the staging deployment validates:**

| Check | `--dry-run=server` (former approach) | Staging deploy to `bank-marketing-dev` (current) |
|---|---|---|
| YAML schema compliance | Yes | Yes |
| Admission controller policies | Yes | Yes |
| Resource quota violations | Yes | Yes |
| Namespace existence | Yes | Yes |
| Image pull from ACR succeeds | No | Yes |
| Pod scheduling on real nodes | No | Yes |
| Container startup (model loads) | No | Yes |
| Health probe passes in-cluster | No | Yes |
| K8s service routing works | No | Yes |

### CD Stage — Production Deployment (Merge → `main`)

On merge to `main`, the CD stage downloads the model artifacts, builds and pushes the production inference image to ACR, deploys to AKS, and runs a live smoke test against the external endpoint.

1. Download `model-artifacts` from the TrainModel stage
2. Stage `model.pkl` into `artifacts/` for the Docker build context
3. Build and push inference image to ACR as `<buildId>` + `latest`
4. Deploy to `bank-marketing` namespace via `KubernetesManifest@1`
5. Live smoke test — wait for LoadBalancer IP, then `GET /health`

| Step | Purpose |
|---|---|
| Download model artifacts | Get `model.pkl` + `metrics.json` produced by TrainModel stage |
| Build + push inference image | Build `Dockerfile.infer` with model baked in, push to ACR with commit SHA + `latest` tags |
| Deploy to AKS | Apply K8s manifests with the new image tag via `KubernetesManifest@1` |
| Environment gate | `production` environment enforces manual approval before deploy |
| Live smoke test | Validate the deployed service responds on its external LoadBalancer IP |
                  inputs:
                    containerRegistry: '$(ACR_SERVICE_CONNECTION)'
                    repository: 'bank-marketing-api'
                    command: buildAndPush
                    Dockerfile: '**/Dockerfile'
                    tags: |
                      $(Build.SourceVersion)
                      latest

                - task: KubernetesManifest@1
                  displayName: 'Deploy to AKS'
                  inputs:
                    action: deploy
                    connectionType: azureResourceManager
                    azureSubscriptionConnection: '$(AZURE_SUBSCRIPTION)'
                    azureResourceGroup: '$(RESOURCE_GROUP)'
                    kubernetesCluster: '$(AKS_CLUSTER)'
                    manifests: |
                      k8s/deployment.yaml
                      k8s/service.yaml
                    containers: |
                      $(ACR_NAME).azurecr.io/bank-marketing-api:$(Build.SourceVersion)

                - script: |
                    API_URL=$(kubectl get svc bank-marketing-api \
                      -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
                    curl -f http://$API_URL/health
                  displayName: 'Live smoke test — GET /health'
```

| Step | Purpose |
|---|---|
| Docker build + push | Build production image, push to ACR with commit SHA + `latest` tags |
| Deploy to AKS | Apply K8s manifests with the new image tag via `KubernetesManifest@1` |
| Environment gate | `production` environment can enforce manual approval before deploy |
| Live smoke test | Validate the deployed service responds on its external LoadBalancer IP |

### Pipeline 3: Retraining (`retrain.yml`)

> **Pipeline file:** [`.ado/retrain.yml`](../.ado/retrain.yml)

The retraining pipeline is **not triggered by code pushes**. It handles data-driven model updates independently:

| Trigger | When |
|---|---|
| Scheduled | Weekly — Sunday 02:00 UTC |
| Manual | ADO UI → Pipelines → retrain → Run pipeline |
| Event-driven (future) | POST to ADO Pipelines REST API from a drift alert |

**Prerequisite:** The `TrainModel` stage in Pipeline 2 must have pushed `train-latest` to ACR.

**Stages:**

| Stage | Purpose |
|---|---|
| `Retrain` | Download versioned training data from Azure Blob Storage, pull `train-latest` image from ACR (no rebuild), run training, publish model artifacts |
| `ValidateModel` | Download production baseline metrics from Blob Storage, compare new ROC-AUC — fail if regression > 2 percentage points |
| `DeployStaging` | Build inference image with retrained model, push to ACR as `retrain-staging-<buildId>`, deploy to `bank-marketing-dev`, in-cluster smoke test |
| `DeployProduction` | Manual approval gate (`production` environment), build + push inference image as `retrain-<buildId>` + `latest`, deploy to `bank-marketing`, update baseline metrics in Blob Storage |

### Branch Toggle Mechanism

Both CD stages in Pipeline 2 use the branch name to select which stage runs. The `bank-marketing-vars` variable group provides shared configuration, and `Build.SourceBranchName` determines the deployment target:

```yaml
condition: and(succeeded(), eq(variables['Build.SourceBranchName'], 'dev'))   # CD_Dev
condition: and(succeeded(), eq(variables['Build.SourceBranchName'], 'main'))  # CD_Main
```

Only one CD stage executes per pipeline run — they are mutually exclusive. The CI and TrainModel stages always run regardless of branch.

---

## Artifact Flow

```mermaid
flowchart LR
    subgraph Source["Source Code"]
        CODE["src/ + main.py +\nconfig.yaml"]
        REQS_TRAIN["requirements.txt"]
        REQS_INFER["requirements-infer.txt"]
    end

    subgraph TrainBuild["Training Container Build"]
        TRAIN_IMG["Dockerfile.train\n→ training image"]
    end

    subgraph TrainRun["Training Container Run"]
        TRAIN_EXEC["python main.py train\n(data/ + artifacts/ mounted)"]
        MODEL["model.pkl +\nmetrics.json"]
    end

    subgraph InferBuild["Inference Container Build"]
        INFER_IMG["Dockerfile.infer\n→ inference image\n(model.pkl COPY'd)"]
    end

    subgraph Registry["ACR"]
        VT["train-latest"]
        V1["infer:&lt;buildId&gt;"]
        VL["infer:latest"]
        VD["infer:dev-&lt;buildId&gt;"]
    end

    subgraph Runtime["AKS"]
        POD_PROD["Pod (bank-marketing)\nFastAPI + Uvicorn"]
        POD_DEV["Pod (bank-marketing-dev)\nFastAPI + Uvicorn"]
    end

    CODE --> TRAIN_IMG
    REQS_TRAIN --> TRAIN_IMG
    TRAIN_IMG --> TRAIN_EXEC
    TRAIN_EXEC --> MODEL
    MODEL --> INFER_IMG
    CODE --> INFER_IMG
    REQS_INFER --> INFER_IMG
    TRAIN_IMG --> VT
    INFER_IMG --> V1
    INFER_IMG --> VL
    INFER_IMG --> VD
    V1 --> POD_PROD
    VD --> POD_DEV
```

### What goes into the training image

| Content | Purpose |
|---|---|
| `src/` | ML pipeline source code |
| `main.py` | CLI entrypoint (`python main.py train`) |
| `config.yaml` | Runtime configuration |
| `requirements.txt` | Core ML dependencies (pandas, scikit-learn, numpy, joblib, pyyaml) |

### What goes into the inference image

| Content | Purpose |
|---|---|
| `src/` | ML pipeline source + API serving code |
| `config.yaml` | Runtime configuration |
| `artifacts/model.pkl` | Trained model artifact (baked in via `COPY` after training stage) |
| `requirements-infer.txt` | Inference dependencies (fastapi, uvicorn, scikit-learn, pandas, pydantic, numpy, joblib, pyyaml) |

### What stays outside the images

| Content | Reason |
|---|---|
| `data/raw/` | Training data not needed at inference time |
| `notebooks/` | Exploration only — not production code |
| `tests/` | Run in CI, not in production container |
| `artifacts/metrics.json` | Evaluation record — tracked in Git, not needed at runtime |

---

## Pipeline Variables

All variables are stored in the `bank-marketing-vars` variable group in Azure DevOps.

| Variable | Description | Example | Used By |
|---|---|---|---|
| `ACR_SERVICE_CONNECTION` | Azure DevOps service connection to ACR | `acr-connection` | P1, P2, P3 |
| `ACR_NAME` | ACR registry name | `bankmarketingacr` | P2, P3 |
| `AKS_CLUSTER` | AKS cluster name | `bank-marketing-aks` | P2, P3 |
| `RESOURCE_GROUP` | Azure resource group | `rg-bank-marketing` | P2, P3 |
| `AZURE_SUBSCRIPTION` | Azure subscription service connection | `azure-sub-connection` | P2, P3 |
| `TRAIN_IMAGE_NAME` | Training image repository name in ACR | `bank-marketing-train` | P2, P3 |
| `INFER_IMAGE_NAME` | Inference image repository name in ACR | `bank-marketing-api` | P2, P3 |
| `BLOB_STORAGE_ACCOUNT` | Azure Storage account for training data and baselines | `bankmarketingdata` | P3 |
| `BLOB_CONTAINER_TRAINING` | Blob container holding versioned training CSVs | `training-data` | P3 |

---

## Pipeline Conditions

This project uses **namespace-based environment isolation** — two Kubernetes namespaces within the same AKS cluster (`bank-marketing` for production, `bank-marketing-dev` for staging) — combined with a three-pipeline CI/CD architecture. Pre-merge checks are identical for both target branches; only the post-merge CD stage differs.

### Pipeline 1: `pr-validation.yml` (Branch Policy)

| Trigger | Tests | K8s Validation | Train Build + Run | Infer Build | Container Smoke | Push to ACR | Deploy to AKS |
|---|---|---|---|---|---|---|---|
| PR → `dev` | Yes | Yes | Yes (local) | Yes (local) | Yes (local) | No | No |
| PR → `main` | Yes | Yes | Yes (local) | Yes (local) | Yes (local) | No | No |

PR validation is **identical** for both target branches — no conditions, no branching logic.

### Pipeline 2: `azure-pipelines.yml` (Push trigger)

| Trigger | Tests | K8s Validation | TrainModel | Infer Build + Push | Deploy to AKS | Smoke Test |
|---|---|---|---|---|---|---|
| Merge → `dev` | Yes | Yes | Yes (push `train-latest`) | Yes (`dev-<buildId>`) | Yes (`bank-marketing-dev`) | In-cluster (`kubectl exec`) |
| Merge → `main` | Yes | Yes | Yes (push `train-latest`) | Yes (`<buildId>` + `latest`) | Yes (`bank-marketing`) | Live (external IP) |

The CI and TrainModel stages always run on both branches. The only branching logic is the `condition:` on the two mutually exclusive CD stages.

### Pipeline 3: `retrain.yml` (Scheduled / Manual)

| Trigger | Train | Validate | Deploy Staging | Deploy Production |
|---|---|---|---|---|
| Weekly cron / Manual / Drift alert | Pull `train-latest`, run on new data | ROC-AUC quality gate (fail if regression > 2%) | Build infer image, deploy to `bank-marketing-dev`, smoke test | Manual approval, deploy to `bank-marketing`, update baseline |

---

## Future Enhancements

Ephemeral per-PR Review Apps and other planned improvements beyond the current namespace-isolation model are documented in [docs/future-enhancements.md](future-enhancements.md).

---

## Key References

> Reference numbers correspond to [REFERENCES.md](../REFERENCES.md).

- **[11]** Microsoft. [Build and deploy to Azure Kubernetes Service with Azure Pipelines](https://learn.microsoft.com/en-us/azure/aks/devops-pipeline). Step-by-step walkthrough for the AKS DevOps pipeline pattern this project implements — covers Docker@2 build task, ACR push, and KubernetesManifest@1 deploy task.
- **[12]** Microsoft. [Build a CI/CD pipeline for microservices on Kubernetes with Azure DevOps and Helm](https://learn.microsoft.com/en-us/azure/architecture/microservices/ci-cd-kubernetes). Architecture-level guide covering validation builds, full CI/CD flow, environment isolation, and container best practices — the design model for this two-pipeline architecture.
- **[26]** Microsoft. [Pipeline conditions](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/conditions). `Build.SourceBranch` and `Build.Reason` condition expressions used for branch-conditional CD stages.
- **[27]** Microsoft. [YAML templates in pipelines](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/templates). Parameterised template includes and `${{ if }}` expressions — alternative approach for DRY conditional deployment steps.
- **[28]** Microsoft. [Build Azure Repos Git repositories — PR triggers](https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/azure-repos-git#pr-triggers). Documents that Azure Repos Git PR validation requires Branch Policies, not `pr:` in YAML.
- **[20]** Microsoft. [Create your first pipeline — Azure DevOps](https://learn.microsoft.com/en-us/azure/devops/pipelines/create-first-pipeline?view=azure-devops&tabs=python%2Cbrowser). Official quickstart for Azure Pipelines YAML structure — triggers, stages, jobs, and service connections.
- **[23]** Microsoft/Azure. [MLOps v2 — Azure DevOps Deployment Guide](https://github.com/Azure/mlops-v2/blob/main/documentation/deployguides/deployguide_ado.md). Covers service connections, variable groups, and multi-stage pipeline structure for ACR → AKS deployment in the MLOps v2 pattern.
