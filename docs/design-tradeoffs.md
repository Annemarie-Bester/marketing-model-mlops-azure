# Design Tradeoffs

A living record of architectural and engineering decisions made during this project, including what was chosen, what was rejected, and why.

**Format:** Each entry records the decision context, the options considered, the choice made, and the tradeoff accepted.

> Entries are added as decisions are made. Cross-references to `docs/` and `REFERENCES.md` use bracket notation where relevant.

---

## Table of Contents

1. [ML Model & Pipeline](#ml-model--pipeline)
2. [API & Serving](#api--serving)
3. [Infrastructure & Deployment](#infrastructure--deployment)
4. [Local Development](#local-development)
5. [CI/CD & Automation](#cicd--automation)
6. [Observability & Monitoring](#observability--monitoring)

---

## ML Model & Pipeline

### Versioned Azure Blob Storage with manifest over MLflow on ACI for model registry

**Decision:** Use Azure Blob Storage with versioning enabled as a lightweight model registry, rather than deploying a dedicated MLflow Tracking Server on Azure Container Instances.

**Options considered:**
- **MLflow on ACI** — deploy an MLflow server as a Docker container on ACI, backed by Azure Blob Storage for artifact storage and a SQLite/PostgreSQL database for the tracking DB; provides a web UI, `mlflow.search_runs()` API, and a formal model stage lifecycle (`Staging`, `Production`, `Archived`)
- **Azure ML Model Registry** — fully managed service within an Azure ML workspace; deep platform integration with deployment pipelines and model monitoring; requires an Azure ML workspace (~£15–20/month minimum)
- **Versioned Blob Storage with manifest** — enable Blob versioning on the existing storage account; after each training run, write `model.pkl` and capture the Blob version ID; record that ID alongside `git_commit`, `promoted_at`, `roc_auc`, and `accuracy` in a manifest JSON file (`artifacts/registry-manifest.json`)
- **Git-based only** — tag the Git commit that produced each model; no model artifact stored separately from the Docker image bake step

**Choice:** Versioned Blob Storage with manifest

**Reason:**

| Concern | MLflow on ACI | Azure ML Registry | Blob + Manifest | Git only |
|---|---|---|---|---|
| **New infrastructure** | ACI instance, MLflow container, SQL backend | Full Azure ML workspace | Blob versioning on existing storage account (already on the I14 list) | None |
| **Monthly cost** | ~£3–5 (ACI compute) | ~£15–20 (workspace) | Negligible (storage cost for small model files) | Free |
| **Operational surface** | New service to patch, restart, and monitor | Fully managed | None — Blob Storage already provisioned | None |
| **Model promotion** | Formal `transition_model_version_stage()` API call | Managed pipeline | Update `promoted_at` field in manifest, commit, push | Re-tag Git commit |
| **Cross-run comparison** | Web UI + `mlflow.search_runs()` | Managed UI | Compare manifest files or `metrics.json` across Git tags | Manual |
| **Rollback** | Stage transition + redeploy | Managed | Pin image build to a previous Blob version ID from manifest | `git checkout <tag>` |
| **Code changes** | `mlflow.log_*` throughout `src/train.py`, `src/evaluate.py`, `main.py` | Azure ML SDK changes throughout | Write manifest in `main.py train` after existing `joblib.dump()` call | None |

**Manifest schema** (`artifacts/registry-manifest.json`):

```json
{
  "git_commit": "a3f5e21",
  "blob_version_id": "01D8A3F5E21B4C7D...",
  "promoted_at": "2026-03-24T12:00:00Z",
  "roc_auc": 0.912,
  "accuracy": 0.899
}
```

**Tradeoff accepted:** The Blob + Manifest approach does not provide MLflow's cross-run experiment comparison UI, formal stage lifecycle with approval gates, or automatic parameter/metric logging from training runs. At case study scale — one model type, weekly retraining, a single promotion path — these capabilities deliver no material operational value. Their absence removes an entire service from the operational surface proportionately.

**When to upgrade to MLflow:** When the project needs to compare more than a handful of experimental runs simultaneously, enforce a formal `Staging → Production` gate with team approval, or integrate with a downstream system that queries the MLflow Model Registry API. See [future-enhancements.md § MLflow on ACI](future-enhancements.md#mlflow-on-aci--model-registry-upgrade) for the implementation plan.

### Fairlearn in-pipeline fairness assessment over Azure ML RAI Dashboard

**Decision:** Compute fairness metrics directly in `src/evaluate.py` using Fairlearn, rather than generating a full Responsible AI dashboard via Azure ML, or addressing fairness through documentation only.

**Options considered:**
- **Fairlearn in-pipeline** — add `fairlearn` to `requirements.txt`; compute demographic parity difference and equalised odds in `src/evaluate.py` alongside existing accuracy/AUC metrics; include results in `metrics.json`; add a fairness threshold to the retraining pipeline's quality gate
- **Azure ML RAI Dashboard** — generate an interactive Responsible AI dashboard (fairness, explainability, error analysis) via `raiwidgets` and an Azure ML compute run; requires provisioning an Azure ML workspace
- **Documentation only** — acknowledge fairness considerations in architecture docs with no tooling change

**Choice:** Fairlearn in-pipeline

**Reason:**

| Concern | Documentation only | Fairlearn in-pipeline | Azure ML RAI Dashboard |
|---|---|---|---|
| **Fairness visibility** | None — issues only surface post-deployment | Metrics in every training run; regressions caught at the quality gate | Comprehensive interactive analysis including error heatmaps and counterfactuals |
| **New dependencies** | None | `fairlearn` (~15 MB, zero transitive deps beyond scikit-learn which is already present) | `raiwidgets`, `responsibleai`, `azure-ml-sdk` — significant dependency surface |
| **New Azure resources** | None | None | Azure ML workspace (~£15–20/month minimum for compute) |
| **Integration point** | N/A | `src/evaluate.py` alongside existing `roc_auc`/`accuracy` computation | Separate pipeline stage requiring Azure ML compute |
| **Quality gate integration** | N/A | Add `demographic_parity_difference < threshold` to `retrain.yml` ValidateModel stage | Possible but requires Azure ML SDK in the pipeline agent |
| **Portfolio signal** | Weak — awareness but no evidence | Strong — fairness metrics are measured, tracked, and gated | Strongest, but disproportionate for a single-model case study |

**Sensitive features assessed:**

| Feature | Fairness concern |
|---|---|
| `age` (binned) | Age-based discrimination in financial product eligibility |
| `marital` | Proxy for household income; potential disparate impact |
| `education` | Socioeconomic proxy; correlated with creditworthiness proxies |

**Metrics added to `metrics.json`:**
- `demographic_parity_difference` — max difference in positive prediction rate across groups
- `equalized_odds_difference` — max difference in true/false positive rates across groups

**Tradeoff accepted:** Fairlearn metrics measure outcome disparity but do not explain causal sources of bias (that requires SHAP/LIME explainability, available separately). The dashboard's interactive error analysis is deferred — it is most valuable when debugging an underperforming subgroup, which requires production traffic data not yet available.

**When to revisit:** When the model handles real customer data, when a regulatory obligation requires documented fairness evidence (e.g., Fair Lending Act, ECOA for financial services), or when a specific subgroup underperformance is identified in production monitoring.

---

## API & Serving

### FastAPI API key middleware over NGINX Ingress Controller for authentication

**Decision:** Authenticate API requests using a FastAPI middleware function that validates an `X-API-Key` header, rather than deploying an NGINX Ingress Controller with header-based authentication.

**Options considered:**
- **NGINX Ingress Controller** — deploy via Helm chart, convert `LoadBalancer` Service to `ClusterIP`, create an `Ingress` resource with annotations for API key validation, rate limiting, and TLS termination (via cert-manager + Let's Encrypt)
- **Azure API Management (APIM) Consumption tier** — managed API gateway with built-in auth, rate limiting, and analytics; first 1M calls/month free
- **FastAPI API key middleware** — store key in a Kubernetes Secret → inject as env var (`API_KEY`) → validate `X-API-Key` header in a `Depends()` function; return 401 on mismatch

**Choice:** FastAPI API key middleware

**Reason:**

| Concern | NGINX Ingress Controller | Azure APIM Consumption | FastAPI middleware |
|---|---|---|---|
| **K8s complexity** | Helm chart + `Ingress` resource + cert-manager + `ClusterIssuer` — significant jump for someone new to Kubernetes | No K8s changes, but a new Azure resource to manage | One function in `app.py`, one K8s Secret, one env var reference in deployment manifests |
| **TLS/HTTPS** | Yes (cert-manager + Let's Encrypt) | Yes (built-in) | No — HTTP only (TLS is deferred) |
| **Rate limiting** | Yes (annotation-based) | Yes (built-in policies) | Possible via `slowapi` middleware if needed later |
| **Auth model** | Header validation via NGINX config or Lua | Subscription keys, OAuth 2.0 | Header validation in Python — readable and debuggable |
| **Manifest changes** | Replace `LoadBalancer` with `ClusterIP`, add `Ingress`, update CI smoke tests | None (external gateway) | Add `API_KEY` env var from Secret in `deployment.yaml` |
| **Cost** | Free (open-source) | Free at low traffic; cold-start latency (~1–2s) | Free |

**Tradeoff accepted:** This approach does **not** provide TLS/HTTPS. The prediction API accepts customer demographic data (age, balance, marital status) over unencrypted HTTP. For a case study with no real customer data in transit, this is acceptable. For production with real customer data, TLS is mandatory.

### TLS — deferred to NGINX Ingress Controller

TLS termination on AKS requires one of:
- **NGINX Ingress Controller + cert-manager** — automatic Let's Encrypt certificates, free, but adds ~4 Kubernetes resources (Ingress, ClusterIssuer, Certificate, plus the Helm-deployed controller itself)
- **Azure Application Gateway Ingress Controller (AGIC)** — managed, but Application Gateway has a minimum cost of ~£15/month
- **Service Mesh (Istio/Linkerd)** — mTLS between pods, but extreme overkill for a single-service project

The NGINX Ingress path is the correct production answer. It is deferred because:
1. The project currently handles synthetic/public banking data, not real PII
2. The author is new to Kubernetes — understanding Deployments, Services, and Secrets should precede Ingress, cert-manager, and ClusterIssuers
3. The `LoadBalancer` Service, API key authentication, and network policies provide baseline security that is proportionate to the case study scope

**When to revisit:** When the API handles real customer data, when the service is exposed beyond a development/demo context, or when a second service is added (at which point NGINX Ingress provides path-based routing as well as TLS).

---

## Infrastructure & Deployment

### Terraform over Bicep for Infrastructure as Code

**Decision:** Manage all Azure and Kubernetes infrastructure using Terraform with state stored in Azure Blob Storage, rather than Bicep or Pulumi.

**Options considered:**
- **Terraform (AzureRM provider)** — open-source IaC with a mature AzureRM provider, a Kubernetes provider, and a Helm provider; state stored remotely in Azure Blob Storage; plan/apply workflow provides a diff before any change is made; large ecosystem of community modules
- **Bicep** — Azure-native DSL that compiles to ARM templates; first-class Azure resource support; tightly integrated with the Azure CLI and Azure Portal; no separate state file (ARM handles state)
- **Pulumi** — general-purpose IaC using real programming languages (Python, TypeScript); supports Azure and Kubernetes natively; state managed by Pulumi Service or self-hosted backend

**Choice:** Terraform

**Reason:**

| Concern | Bicep | Terraform | Pulumi |
|---|---|---|---|
| **Azure resource coverage** | First-class — every Azure resource has official Bicep support | Mature — AzureRM provider covers all resources in this project | Mature — Azure Native provider mirrors ARM API closely |
| **Kubernetes resource management** | No Kubernetes provider — would require a separate `kubectl apply` or Helm step | `kubernetes` and `helm` providers manage K8s resources alongside Azure resources in the same plan | `pulumi_kubernetes` provider — full K8s support |
| **State management** | None — ARM tracks state server-side; no `terraform.tfstate` to manage | Remote backend in Azure Blob Storage; state locking prevents concurrent applies | Pulumi Service (free tier) or self-hosted backend |
| **Plan/diff before apply** | `az deployment what-if` — supported but less granular than Terraform plan | `terraform plan` shows exact resource additions, changes, and deletions before apply | `pulumi preview` — equivalent to `terraform plan` |
| **Import existing resources** | `az bicep decompile` from ARM export — lossy, requires cleanup | `terraform import` — maps existing Azure resources into state without rebuilding them | `pulumi import` — equivalent capability |
| **Learning curve** | Low for Azure-only teams; HCL-like declarative syntax | Medium — HCL syntax, provider docs, state concepts | Higher — requires choosing a programming language and understanding Pulumi's resource model |
| **Community modules** | Azure Verified Modules (growing, official) | Terraform Registry — extensive community modules for AKS, ACR, networking | Pulumi Registry — smaller but growing |
| **CI/CD integration** | `az deployment group create` in ADO pipeline | `terraform init / plan / apply` in ADO pipeline — well-documented pattern | `pulumi up` in ADO pipeline — less common, fewer examples |

**Key differentiator — single toolchain for Azure + Kubernetes:** Bicep cannot manage Kubernetes resources (`Deployment`, `Service`, `NetworkPolicy`, `Secret`). Using Bicep would require a separate step (`kubectl apply` or Helm) for every K8s resource — splitting infrastructure into two toolchains with no unified plan/diff. Terraform's `kubernetes` provider manages both Azure resources and K8s manifests in the same `terraform plan`, producing a single, reviewable change set per deployment.

**State backend configuration:**
```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "bank-marketing-rg"
    storage_account_name = "<storage-account>"
    container_name       = "tfstate"
    key                  = "bank-marketing.tfstate"
  }
}
```

**Tradeoff accepted:** Terraform requires HCL fluency and state management discipline. The `terraform.tfstate` file is sensitive (contains resource IDs and some secrets) and must be stored in the Blob Storage backend with appropriate RBAC — not committed to Git. The `terraform import` migration from the existing CLI-provisioned resources requires careful sequencing: import before plan, verify state accuracy, then apply any drift corrections.

**When to revisit:** If the project migrates to a fully Azure-native toolchain (Azure DevOps + Azure Pipelines + Bicep + AKS) and Kubernetes resource management is handled entirely via Helm or GitOps (Flux/Argo CD), Bicep becomes a more coherent choice for the Azure layer. At current scope, the unified Terraform approach is more maintainable.

---

### Separate train and inference containers over a single unified image

**Decision:** Build two purpose-built Docker images (`Dockerfile.train`, `Dockerfile.infer`) instead of a single image that handles both training and serving.

**Options considered:**
- **Single image** — one `Dockerfile` with all dependencies; switch behaviour via an entrypoint argument (`train` / `serve`)
- **Two images** — a training image that runs `main.py train` and an inference image that runs `uvicorn` with `FastAPI`

**Choice:** Two images

**Reason:**

| Concern | Single image | Two images |
|---|---|---|
| **Image size** | Carries inference deps (FastAPI, uvicorn, pydantic) during training and training-only data I/O during serving | Each image installs only what it needs (`requirements.txt` vs `requirements-infer.txt`) |
| **Attack surface** | Serving container ships with the full training toolchain; wider vulnerability footprint in production | Inference image has no training code, no volume mounts for raw data, and no write paths — smaller attack surface |
| **Scaling independence** | Training and serving share resource profiles; Kubernetes resource requests/limits must accommodate the heavier workload | Inference pods are right-sized (`256Mi–512Mi`, `250m–500m` CPU) without paying for training headroom |
| **Artifact handoff** | Model is produced and consumed inside the same image — implicit coupling | Training uploads `model.pkl` to Azure Blob Storage; inference pods load it at runtime via `MODEL_BLOB_PREFIX` — explicit, auditable handoff |
| **CI/CD clarity** | Single build step, but cache invalidation is coarse (any dep change rebuilds everything) | Two independent build stages; inference image is rebuilt only when the model or serving code changes |

**Tradeoff accepted:** Two Dockerfiles means two build pipelines and two image tags to manage in CI. The model artifact is explicitly transferred between stages via Azure Blob Storage (training uploads it, inference pods download it at runtime via `MODEL_BLOB_PREFIX`). This adds a coordination step but makes the handoff visible and version-trackable rather than implicit.

**File mapping:**
- `Dockerfile.train` → `requirements.txt`, entrypoint `python main.py train`, volumes for `/app/data` and `/app/artifacts`
- `Dockerfile.infer` → `requirements-infer.txt`, entrypoint `uvicorn src.api.app:app`, loads `model.pkl` from Azure Blob Storage at runtime (or volume mount locally), exposes port 8000

---

## Local Development

### kind over minikube for local Kubernetes

**Decision:** Use `kind` (Kubernetes IN Docker) instead of `minikube` for local cluster management.

**Options considered:**
- `minikube --driver=docker` — widely documented, has a built-in dashboard and addons
- `kind` — minimal, no SSH dependency, designed for CI and containerised environments

**Choice:** `kind`

**Reason:** This project runs inside a devcontainer on WSL2, which uses Docker-outside-of-Docker (DooD). Minikube's Docker driver creates a sibling container on the host and then SSHs into it to bootstrap Kubernetes. That SSH connection times out in the DooD networking model, producing a `DRV_CREATE_TIMEOUT` after 360 seconds every time. `kind` bootstraps Kubernetes entirely through the Docker API with no SSH step, making it compatible with this environment by design.

**Tradeoff accepted:** `kind` has no built-in dashboard, addon system, or `service --url` helper. Port-forwarding (`kubectl port-forward`) is required to access services locally instead of a direct URL. This is an acceptable constraint for a local manifest validation and smoke test workflow.

**Config note:** A `kind-config.yaml` file at the repo root sets `cgroupDriver: cgroupfs` via `kubeadmConfigPatches`. This is required because WSL2 uses cgroupfs v1, while kind's default kubelet configuration assumes `systemd`. Without this patch the control-plane fails to start with a `connection refused` error on port 6443.

### kind cluster startup in DooD requires manual kubeconfig patching

**Decision:** After `kind create cluster`, patch the kubeconfig server address to use the node container's Docker-network IP, and install the CNI plugin manually.

**Context:** `kind create cluster` verifies the cluster is ready by connecting to the API server via `localhost:<port>` from within the devcontainer. In DooD, that port is published on the _host's_ localhost, not the devcontainer's — so kind's readiness check fails with `connection refused` and the command exits with an error, even though the cluster containers have started and the API server is healthy.

**Steps required after `kind create cluster --retain` exits:**
1. Export kubeconfig: `kind export kubeconfig --name bm-local`
2. Get node IP: `docker inspect bm-local-control-plane --format '{{.NetworkSettings.Networks.kind.IPAddress}}'`
3. Patch server: `kubectl config set-cluster kind-bm-local --server=https://<NODE_IP>:6443`
4. Install CNI: `docker exec bm-local-control-plane cat /kind/manifests/default-cni.yaml | sed 's/{{ .PodSubnet }}/10.244.0.0\/24/' | kubectl apply -f -`
5. Wait for Ready: `kubectl wait --for=condition=Ready node --all --timeout=120s`

The CNI manifest must be applied manually because kind's bootstrap sequence installs it via `localhost`, which also fails in DooD. The manifest is baked into the kind node image at `/kind/manifests/default-cni.yaml` and contains a single Go template placeholder (`{{ .PodSubnet }}`) that must be substituted with the pod CIDR (`10.244.0.0/24`).

**Tradeoff accepted:** This is a multi-step manual bootstrap. `--retain` must always be used in this environment — without it, kind deletes the node when its localhost readiness check times out, making the node container unavailable for manual bootstrap (the `admin.conf` missing error). The full workflow is scripted in Section 5 of the Local Development Guide.

---

## CI/CD & Automation

---

## Observability & Monitoring

### OpenTelemetry distro over classic Application Insights SDK

**Decision:** Instrument the inference service using `azure-monitor-opentelemetry` (Microsoft's OpenTelemetry distro for Azure) rather than the classic Application Insights Python SDK (`opencensus-ext-azure` or `applicationinsights`).

**Options considered:**
- **OpenTelemetry SDK + Azure Monitor Exporter** (`azure-monitor-opentelemetry`) — Microsoft-maintained distro that wraps the OTel API/SDK, auto-instruments FastAPI requests, and exports traces, metrics, and logs to App Insights via a single `configure_azure_monitor()` call
- **Classic App Insights SDK** (`opencensus-ext-azure`) — the legacy instrumentation path; simpler to understand but built on OpenCensus, which was retired in early 2025 and is no longer receiving updates
- **Prometheus + Grafana on AKS** — self-hosted metrics stack; well-suited for infrastructure metrics but adds a `kube-prometheus-stack` Helm chart, persistent volumes, and a Grafana deployment; no native integration with the existing App Insights workspace

**Choice:** OpenTelemetry distro (`azure-monitor-opentelemetry`)

**Reason:**

| Concern | Classic SDK (opencensus) | OpenTelemetry distro | Prometheus + Grafana |
|---|---|---|---|
| **Maintenance status** | Deprecated (OpenCensus retired 2025) | Active — Microsoft's strategic direction | Active |
| **FastAPI auto-instrumentation** | Manual request hooks required | `opentelemetry-instrumentation-fastapi` auto-instruments all routes | Via `starlette-exporter` or custom middleware |
| **Azure Monitor integration** | Direct App Insights ingestion | App Insights ingestion via OTLP exporter | Requires Azure Monitor managed Prometheus or remote-write adapter |
| **Custom metrics** | `TelemetryClient.track_metric()` | OTel `Histogram` and `Counter` instruments — vendor-neutral API | Prometheus `Gauge`, `Histogram`, `Counter` — vendor-neutral |
| **Log correlation** | Manual correlation ID threading | Automatic trace context propagation across logs, metrics, and traces | No built-in log correlation |
| **Local dev impact** | Crashes if connection string absent unless guarded | Guarded by `APPLICATIONINSIGHTS_CONNECTION_STRING` env var — silently skipped locally | Requires Prometheus scrape target; not suitable for local dev |
| **New Azure resources** | None (uses existing App Insights) | None (uses existing App Insights) | Prometheus PVC + Grafana deployment on AKS |

**Integration pattern:**

```python
# In the lifespan handler (app.py)
connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(connection_string=connection_string)
    FastAPIInstrumentor.instrument_app(app)
```

The connection string is stored in a Kubernetes Secret and injected as an env var in `k8s/deployment.yaml`. Locally, the var is absent and OTel activation is silently skipped — the app behaves identically to its current state (stdout logging only). Existing `logger.info()` calls in `app.py` are forwarded automatically by OTel's Python logging bridge when active; no changes to individual log statements are required.

**Telemetry landing locations (App Insights / Log Analytics):**

| Signal | Table | Populated by |
|---|---|---|
| HTTP request spans | `requests` | `FastAPIInstrumentor` (automatic) |
| Unhandled exceptions | `exceptions` | OTel exception handler (automatic) |
| Prediction latency | `customMetrics` | Manual `Histogram` instrument in `/predict` |
| Prediction class counts | `customMetrics` | Manual `Counter` instrument in `/predict` |
| `logger.info/warning` records | `traces` | OTel Python logging bridge (automatic once configured) |

**Tradeoff accepted:** The `azure-monitor-opentelemetry` package pulls in several transitive OTel dependencies (`opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-*`), adding ~10–15 MB to the inference image. This is a proportionate cost: the package is the vendor-supported entry point and avoids a future migration away from the deprecated OpenCensus SDK.

**When to revisit:** If the project adds a second service or adopts a service mesh, the OTel foundation here makes distributed tracing across services straightforward via W3C `traceparent` header propagation — no rework needed.

### Structured JSON logging via python-json-logger over format-string logging

**Decision:** Replace Python's default format-string logging with structured JSON output using `python-json-logger`, rather than relying on OpenTelemetry's log exporter alone or retaining format-string logs parsed via regex in Log Analytics.

**Options considered:**
- **`python-json-logger`** — wraps Python's standard `logging.Formatter` to emit each log record as a JSON object; works with the existing `logger.info(...)` call sites unchanged; OTel's Python logging bridge (activated by A4) automatically forwards JSON records to App Insights' `traces` table with all fields parsed
- **OTel log exporter only** — rely on `opentelemetry-instrumentation-logging` to forward records; fields remain bound to the OTel attribute model and are only available when OTel is active; locally, logs revert to format-string output
- **Keep format-string logging** — no code change; App Insights receives a single unstructured string per record; Log Analytics queries require regex extraction to access individual fields (e.g., `prediction`, `latency_ms`)

**Choice:** `python-json-logger`

**Reason:**

| Concern | Format-string logging | OTel exporter only | python-json-logger |
|---|---|---|---|
| **KQL queryability** | Requires `parse` / regex on `message` field | Structured when OTel active, unstructured locally | JSON fields individually addressable in `customDimensions` always |
| **Local dev readability** | Human-readable | Human-readable (format-string fallback) | JSON to stdout — readable with `jq`, parseable by log forwarders |
| **OTel bridge compatibility** | Bridge forwards opaque string | Bridge forwards OTel-attributed record | Bridge forwards structured JSON; all custom fields appear in `customDimensions` in App Insights |
| **Code changes** | None | Minimal (bridge config at startup) | Configure formatter once in logger setup; zero changes to existing `logger.info(...)` call sites |
| **Dependency** | None | Included in `azure-monitor-opentelemetry` | `python-json-logger` (~20 KB, zero transitive deps) |

**Concrete field structure** — each `logger.info()` record will produce a JSON object with at minimum:

```json
{
  "timestamp": "2026-03-24T12:00:00.000Z",
  "level": "INFO",
  "name": "src.api.app",
  "message": "Prediction made",
  "prediction": 1,
  "probability": 0.7832,
  "latency_ms": 12.4
}
```

In App Insights, `prediction`, `probability`, and `latency_ms` appear as individually queryable keys under `customDimensions`, enabling KQL such as:

```kql
traces
| extend prob = todouble(customDimensions["probability"])
| summarize avg(prob), stdev(prob) by bin(timestamp, 1d)
```

**Tradeoff accepted:** JSON logs are less immediately human-readable than format strings when tailing raw stdout. This is mitigated by piping through `jq` locally (`python main.py serve | jq`) and is a standard practice in production Python services.

**Implementation note:** Configure the formatter once in a `logging_config.py` or at the top of `app.py`'s module-level setup. All modules that obtain a logger via `logging.getLogger(__name__)` inherit the JSON formatter automatically — no per-module changes required.
