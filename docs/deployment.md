# Deployment Architecture

AKS deployment structure, API exposure, and container lifecycle for the Bank Marketing prediction service.

The cluster uses **two Kubernetes namespaces** within a single AKS cluster to separate production from staging:

| Namespace | Branch | Replicas | Service type | Purpose |
|---|---|---|---|---|
| `bank-marketing` | `main` | 2 | `LoadBalancer` (external IP) | Production traffic |
| `bank-marketing-dev` | `dev` | 1 | `ClusterIP` (internal only) | Staging smoke tests before promoting to `main` |

This follows Microsoft's [AKS cluster isolation guidance](https://learn.microsoft.com/en-us/azure/aks/operator-best-practices-cluster-isolation) — logical namespace isolation on the same cluster rather than a second cluster, keeping infrastructure cost flat while providing a real Kubernetes deployment gate ahead of production.

---

## AKS Cluster Layout

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
            RQ["ResourceQuota<br/>max 1 CPU · 512Mi memory"]
        end
    end

    ACR["Azure Container Registry<br/>bankmarketingacr"]
    LB["Azure Load Balancer<br/>External IP"]
    CLIENT["Client / Upstream Service"]

    ACR -->|"main: sha + latest"| DEP_PROD
    ACR -->|"dev: dev-sha"| DEP_DEV
    DEP_PROD --> SVC_PROD
    SVC_PROD --> LB
    CLIENT -->|"POST /predict"| LB
    LB --> DEP_PROD
```

---

## Kubernetes Resources

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bank-marketing-api
  namespace: bank-marketing
  labels:
    app: bank-marketing-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: bank-marketing-api
  template:
    metadata:
      labels:
        app: bank-marketing-api
    spec:
      containers:
        - name: api
          image: bankmarketingacr.azurecr.io/bank-marketing-api:latest
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          env:
            - name: UVICORN_WORKERS
              value: "1"
      imagePullSecrets:
        - name: acr-secret
```

| Field | Value | Rationale |
|---|---|---|
| `replicas: 2` | Two pods for basic availability | Single pod = downtime during restarts |
| `containerPort: 8000` | Matches `config.yaml` API port | Consistent with `uvicorn` default in config |
| CPU request: 250m | Quarter-core baseline | Logistic regression inference is lightweight |
| Memory request: 256Mi | Sufficient for sklearn model in memory | `model.pkl` is small (< 10MB) |
| CPU limit: 500m | Cap burst CPU usage | Prevents noisy-neighbour issues |
| Memory limit: 512Mi | Hard ceiling | Prevents OOM from affecting other pods |

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: bank-marketing-api
  namespace: bank-marketing
spec:
  type: LoadBalancer
  selector:
    app: bank-marketing-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
```

| Field | Value | Rationale |
|---|---|---|
| `type: LoadBalancer` | Provisions Azure Load Balancer with external IP | Simplest external access for a single service |
| `port: 80` | External-facing port | Standard HTTP port for consumers |
| `targetPort: 8000` | Pod's container port | Maps to FastAPI/Uvicorn listening port |

---

## Staging Namespace — `bank-marketing-dev`

The staging namespace mirrors the production configuration with three deliberate differences: one replica (sufficient for smoke testing), a `ClusterIP` service (no external exposure), and a `ResourceQuota` that caps resource consumption so the staging workload cannot compete with production pods on shared nodes.

### Staging Deployment

```yaml
# k8s/deployment-dev.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bank-marketing-api
  namespace: bank-marketing-dev
  labels:
    app: bank-marketing-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bank-marketing-api
  template:
    metadata:
      labels:
        app: bank-marketing-api
    spec:
      containers:
        - name: api
          image: bankmarketingacr.azurecr.io/bank-marketing-api:dev-latest
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          env:
            - name: UVICORN_WORKERS
              value: "1"
```

### Staging Service

```yaml
# k8s/service-dev.yaml
apiVersion: v1
kind: Service
metadata:
  name: bank-marketing-api
  namespace: bank-marketing-dev
spec:
  type: ClusterIP
  selector:
    app: bank-marketing-api
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
```

| Field | Value | Rationale |
|---|---|---|
| `type: ClusterIP` | Internal cluster IP only — no external load balancer | Staging endpoint is consumed only by the CI pipeline smoke test, never by real traffic |
| `port: 8000` | Matches container port | No port translation needed — consumed internally via `kubectl exec` or `kubectl port-forward` |

### Staging ResourceQuota

```yaml
# k8s/quota-dev.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: bank-marketing-dev-quota
  namespace: bank-marketing-dev
spec:
  hard:
    requests.cpu: "250m"
    requests.memory: "256Mi"
    limits.cpu: "500m"
    limits.memory: "512Mi"
    pods: "2"
```

| Field | Value | Rationale |
|---|---|---|
| CPU limit | 500m | Matches single-replica pod limit — prevents the namespace from requesting more |
| Memory limit | 512Mi | Matches single-replica pod limit |
| `pods: "2"` | Maximum two pods | Allows one running pod plus one rollout surge; prevents accidental over-provisioning |

---

## API Exposure

```mermaid
sequenceDiagram
    participant C as Client
    participant LB as Azure Load Balancer
    participant S as K8s Service
    participant P as Pod (FastAPI)
    participant M as model.pkl

    C->>LB: POST /predict (JSON)
    LB->>S: Route to healthy pod
    S->>P: Forward request
    P->>P: Pydantic validation
    P->>P: clean_data() transforms
    P->>M: pipeline.predict()
    M-->>P: prediction + probability
    P-->>S: JSON response
    S-->>LB: Forward response
    LB-->>C: {"prediction": 1, "probability": 0.73, "label": "yes"}
```

### Endpoints

| Method | Path | Purpose | Used By |
|---|---|---|---|
| `POST` | `/predict` | Score a single customer record | Upstream services, batch callers |
| `GET` | `/health` | Liveness/readiness probe | Kubernetes, CI smoke tests |
| `GET` | `/docs` | Auto-generated OpenAPI documentation | Developers (FastAPI built-in) |

---

## Container Lifecycle

```mermaid
flowchart TD
    BUILD["CI: Docker build"] --> PUSH_Q{"Branch?"}
    PUSH_Q -->|"main"| PUSH_PROD["Push to ACR<br/>tags: sha + latest"]
    PUSH_Q -->|"dev"| PUSH_DEV["Push to ACR<br/>tag: dev-sha"]

    PUSH_PROD --> DEPLOY_PROD["kubectl apply<br/>namespace: bank-marketing"]
    PUSH_DEV --> DEPLOY_DEV["kubectl apply<br/>namespace: bank-marketing-dev"]

    DEPLOY_PROD --> SCHEDULE_PROD["Kubernetes schedules pods (2 replicas)"]
    DEPLOY_DEV --> SCHEDULE_DEV["Kubernetes schedules pod (1 replica)"]

    SCHEDULE_PROD --> PULL_PROD["Pod pulls image from ACR"]
    SCHEDULE_DEV --> PULL_DEV["Pod pulls image from ACR"]

    PULL_PROD --> START_PROD["Container starts:<br/>uvicorn loads model.pkl"]
    PULL_DEV --> START_DEV["Container starts:<br/>uvicorn loads model.pkl"]

    START_PROD --> READY_PROD["Readiness probe passes:<br/>GET /health → 200"]
    START_DEV --> READY_DEV["Readiness probe passes:<br/>GET /health → 200"]

    READY_PROD --> LIVE["Pod receives external traffic"]
    READY_DEV --> SMOKE["CD_Dev smoke test:<br/>kubectl exec → POST /predict"]

    LIVE --> LIVENESS["Liveness probe:<br/>periodic GET /health"]
    LIVENESS -->|"fails 3x"| RESTART["Pod restarted"]
    RESTART --> START_PROD
```

### Startup Sequence

The sequence below applies to both namespaces. The only difference is the deployment target and what happens once the pod is ready.

1. **Image pull**: Kubernetes pulls the container image from ACR using the managed identity `AcrPull` role (`--attach-acr`)
2. **Container start**: Uvicorn starts, FastAPI lifespan handler loads `model.pkl` into memory
3. **Readiness probe**: Kubernetes polls `GET /health` — pod only receives traffic once it returns 200
4. **Live traffic** (`bank-marketing`): Service routes external requests through the Azure Load Balancer
5. **Smoke test** (`bank-marketing-dev`): The CD pipeline runs `kubectl exec` or `kubectl port-forward` to issue a `POST /predict` request against the internal `ClusterIP` service, confirming the model loads and returns a valid prediction before the change is eligible to merge to `main`
6. **Liveness monitoring** (`bank-marketing`): Kubernetes periodically checks `/health` — restarts the pod if 3 consecutive probes fail

### Rolling Update Strategy

When a new image is deployed:

1. Kubernetes creates new pods with the updated image
2. New pods must pass readiness probes before receiving traffic
3. Old pods are drained (stop receiving new requests, finish in-flight)
4. Old pods are terminated
5. Zero-downtime deployment with `replicas >= 2`

---

## Resource Sizing Rationale

This is a lightweight inference workload:

- **Model**: Logistic Regression with sklearn preprocessing (small memory footprint)
- **Throughput**: Single-record predictions, not batch — low CPU per request
- **Latency target**: < 100ms per prediction (measured in `app.py`)
- **Scale**: 2 replicas handle moderate traffic; HPA can be added for auto-scaling

---

## Key References

> Reference numbers correspond to [REFERENCES.md](../REFERENCES.md).

- **[11]** Microsoft. [Build and deploy to Azure Kubernetes Service with Azure Pipelines](https://learn.microsoft.com/en-us/azure/aks/devops-pipeline). Full two-stage pipeline walkthrough (Build → Deploy) with Docker@2 and KubernetesManifest@1 tasks — the CI/CD pattern this deployment configuration is designed to receive.
- **[29]** Microsoft. [Core concepts for Azure Kubernetes Service (AKS)](https://learn.microsoft.com/en-us/azure/aks/concepts-clusters-workloads). Foundational reference for AKS `Deployment` and `Service` resources, pod scheduling, node pools, and the Kubernetes primitives used throughout this document.
- **[21]** Microsoft. [Deploy a machine learning model to Azure Kubernetes Service (v1)](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-azure-kubernetes-service?view=azureml-api-1&tabs=python). Reference for AKS inference configuration — health probe setup, resource limits, and deployment configuration patterns applicable to the serving layer.
- **[24]** Microsoft. [Quickstart: Create an Azure Container Registry using Terraform](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-get-started-terraform?tabs=azure-cli). ACR provisioning reference covering SKU selection, admin user configuration, and AKS integration via `imagePullSecrets` — the mechanism used in `k8s/deployment.yaml`.

For this case study, fixed replicas are sufficient. A `HorizontalPodAutoscaler` would be the next step for production scale.
