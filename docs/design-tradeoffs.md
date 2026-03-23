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

---

## ML Model & Pipeline

---

## API & Serving

---

## Infrastructure & Deployment

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
