# References

Bibliography for the Bank Marketing MLOps project, organised by repository component.


**Format:** `[N]. Author(s) or Organisation. *Title*. Publisher / URL. Year.`
Leave a `> Note:` line beneath an entry to record why it was useful.

---

## Table of Contents

1. [Root — Pipeline & Configuration](#root--pipeline--configuration)
2. [src/ — Core ML Pipeline](#src--core-ml-pipeline)
3. [src/api/ — Model Serving](#srcapi--model-serving)
4. [tests/ — Testing](#tests--testing)
5. [data/ — Dataset](#data--dataset)
6. [artifacts/ — Model Artifacts](#artifacts--model-artifacts)
7. [notebooks/ — Exploratory Analysis](#notebooks--exploratory-analysis)
8. [.github/ — CI/CD & Agents](#github--cicd--agents)

---

## Root — Pipeline & Configuration

*Topics: ML pipeline design, config-driven execution, CLI entry points, dependency management.*

<!-- Add sources below as you read them -->

---

## `src/` — Core ML Pipeline

*Topics: scikit-learn pipelines, feature engineering, class imbalance, logistic regression, gradient boosting, random forests, model evaluation metrics (ROC-AUC, F1).*

<!-- Add sources below as you read them -->

---

## `src/api/` — Model Serving

*Topics: FastAPI, REST API design, Pydantic validation, model serving patterns, containerisation, uvicorn.*

<!-- Add sources below as you read them -->

---

## `tests/` — Testing

*Topics: pytest, test fixtures, API testing with TestClient, unit vs integration testing, in-memory test data.*

<!-- Add sources below as you read them -->

---

## `data/` — Dataset

*Topics: UCI Bank Marketing dataset, class imbalance, feature distributions, data leakage.*

<!-- Add sources below as you read them -->

---

## `artifacts/` — Model Artifacts

*Topics: Model serialisation (joblib/pickle), artifact management, model versioning.*

<!-- Add sources below as you read them -->

---

## `notebooks/` — Exploratory Analysis

*Topics: EDA methodology, skewness and transforms, visualisation, feature selection.*

<!-- Add sources below as you read them -->

---

## `.github/` — CI/CD & Agents

*Topics: Azure DevOps Pipelines, AKS deployment, Docker, Azure Container Registry, MLOps, VS Code agent customisation.*

### CI/CD Pipelines — Azure DevOps + AKS

[1]. Microsoft. *Build and deploy to Azure Kubernetes Service with Azure Pipelines*. https://learn.microsoft.com/en-us/azure/aks/devops-pipeline. 2025.
> Step-by-step walkthrough: create ACR, AKS cluster, and a two-stage Azure DevOps pipeline (Build → Deploy) with Docker@2 and KubernetesManifest@1 tasks.

[2]. Microsoft. *Build a CI/CD pipeline for microservices on Kubernetes with Azure DevOps and Helm*. https://learn.microsoft.com/en-us/azure/architecture/microservices/ci-cd-kubernetes. 2024.
> Architecture-level guide covering validation builds, full CI/CD flow, Helm chart packaging, environment isolation, and container best practices.

[3]. Microsoft. *Azure MLOps v2 — GitHub repository*. https://github.com/Azure/mlops-v2. 2024.
> Deployable sample templates for the MLOps v2 architecture, including CI/CD pipeline definitions for classical ML scenarios.

[4]. Microsoft/Azure. *AzureML Examples — Kubernetes Online Endpoint Simple Deployment*. https://github.com/Azure/azureml-examples/blob/main/sdk/python/endpoints/online/kubernetes/kubernetes-online-endpoints-simple-deployment.ipynb. GitHub, 2024.
> End-to-end SDK example: create a Kubernetes online endpoint, configure a custom container deployment, and validate predictions — reference for understanding the full AzureML endpoint lifecycle on AKS.

[5]. Microsoft/Azure. *AzureML Examples — Setup Scripts*. https://github.com/Azure/azureml-examples/tree/main/setup. GitHub, 2024.
> Infrastructure setup scripts for the AzureML examples repository — compute cluster and workspace provisioning patterns referenced during cluster and workspace setup research.

[6]. Microsoft/Azure. *AzureML Examples — CLI Kubernetes Online Endpoints*. https://github.com/Azure/azureml-examples/tree/main/cli/endpoints/online/kubernetes. GitHub, 2024.
> CLI-based deployment examples for Kubernetes online endpoints — covers `endpoint.yml` and `deployment.yml` patterns for registering custom containers as AzureML online endpoints.

[7]. Microsoft. *Online Endpoints — Managed vs Kubernetes Online Endpoints*. https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#managed-online-endpoints-vs-kubernetes-online-endpoints. 2024.
> Compares Azure-managed online endpoints with customer-managed Kubernetes online endpoints — informed the architectural decision to use direct AKS deployment over AzureML managed endpoints for this project.

[8]. Microsoft. *Deploy a custom container to an Azure Machine Learning online endpoint*. https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-custom-container?view=azureml-api-2&tabs=cli. 2024.
> Step-by-step guide for packaging a custom Docker container and registering it as an AzureML online endpoint — covers container specs, scoring scripts, and environment configuration.

[9]. Microsoft. *Online Endpoints — Local Debugging with Local Endpoint*. https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#local-debugging-with-local-endpoint. 2024.
> Describes how to test a container image locally before pushing to AKS — local endpoint debugging pattern used to validate the model container before CI/CD deployment.

[10]. Microsoft. *Create your first pipeline — Azure DevOps*. https://learn.microsoft.com/en-us/azure/devops/pipelines/create-first-pipeline?view=azure-devops&tabs=python%2Cbrowser. 2025.
> Official Azure Pipelines quickstart: connect a repository, create a YAML pipeline, configure triggers, and understand pipeline stages — foundational reference for the project's `azure-pipelines.yml` structure.

[11]. Microsoft. *Deploy a machine learning model to Azure Kubernetes Service (v1)*. https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-azure-kubernetes-service?view=azureml-api-1&tabs=python. 2024.
> AzureML SDK v1 reference for deploying registered models to AKS — covers inference configuration, deployment configuration, and health probe setup on AKS clusters.

[12]. Microsoft/Azure. *MLOps v2 — Classical ML Architecture Diagram*. https://github.com/Azure/mlops-v2/blob/main/documentation/architecture/media/AzureML_CML_Architecture.png. GitHub, 2024.
> Visual reference for the AzureML MLOps v2 classical ML architecture — shows the relationship between CI/CD pipelines, model registry, and AKS serving; used as the architectural benchmark for this project's GitHub → ADO → ACR → AKS design.

[13]. Microsoft/Azure. *MLOps v2 — Azure DevOps Deployment Guide*. https://github.com/Azure/mlops-v2/blob/main/documentation/deployguides/deployguide_ado.md. GitHub, 2024.
> Step-by-step deployment guide for provisioning the MLOps v2 infrastructure using Azure DevOps — covers service connections, variable groups, and multi-stage pipeline structure for ACR → AKS deployment.

[14]. Microsoft. *Quickstart: Create an Azure Container Registry using Terraform*. https://learn.microsoft.com/en-us/azure/container-registry/container-registry-get-started-terraform?tabs=azure-cli. 2024.
> Terraform-based ACR provisioning reference — covers registry SKU selection, admin user configuration, and AKS integration via `imagePullSecrets`; referenced when researching ACR setup options.

### MLOps Lifecycle & Maturity

[15]. Microsoft. *Machine learning operations (MLOps v2)*. https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/machine-learning-operations-v2. 2024.
> Canonical Azure MLOps reference — inner loop (model development) → outer loop (model deployment) lifecycle with CI/CD pipelines promoting models through staging → production on AKS.

[16]. Microsoft. *MLOps maturity model*. https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model. 2025.
> Five maturity levels (0–4) for assessing MLOps capability. Useful for framing current state and target state.

[17]. Microsoft. *MLOps and GenAIOps for AI workloads*. https://learn.microsoft.com/en-us/azure/well-architected/ai/mlops-genaiops. 2024.
> Azure Well-Architected Framework perspective on why ML workloads need specialised operations.

### Azure Architecture & Platform

[18]. Microsoft. *Core concepts for Azure Kubernetes Service (AKS)*. https://learn.microsoft.com/en-us/azure/aks/concepts-clusters-workloads. 2025.
> Foundational reference for AKS clusters, node pools, pods, namespaces, and pricing tiers.

[19]. Microsoft. *What is Azure Pipelines?*. https://learn.microsoft.com/en-us/azure/devops/pipelines/get-started/what-is-azure-pipelines. 2024.
> Official Azure Pipelines entry point — build/release pipelines, YAML syntax, service connections, and environments.

[20]. Microsoft. *Introduction to Container registries in Azure*. https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro. 2024.
> ACR creation, repository namespaces, image tagging strategies, and Helm chart storage.

[21]. Microsoft. *End-to-end MLOps with Azure Machine Learning (Learning Path)*. https://learn.microsoft.com/en-us/training/paths/build-first-machine-operations-workflow. 2024.
> Hands-on training path for building a first MLOps workflow.

[22]. Microsoft. *GitOps for Azure Kubernetes Service*. https://learn.microsoft.com/en-us/azure/architecture/example-scenario/gitops-aks/gitops-blueprint-aks. 2024.
> Alternative pull-based deployment model using Flux/ArgoCD — worth considering for production maturity.

### Cluster Isolation & Deployment Simulation

[23]. Microsoft. *Best practices for cluster isolation in Azure Kubernetes Service (AKS)*. https://learn.microsoft.com/en-us/azure/aks/operator-best-practices-cluster-isolation. 2024.
> Logical (namespace) vs. physical (multi-cluster) isolation patterns. Recommends namespace-based isolation for dev/test environments within a shared cluster to minimise cost and management overhead.

[24]. Microsoft. *Kubernetes resources in environments*. https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments-kubernetes. 2025.
> Azure DevOps Review Apps — deploy every PR to a dynamic ephemeral namespace. Includes complete YAML pipeline example with `DeployPullRequest` jobs, dynamic namespace creation, and PR comment automation.

[25]. Kubernetes. *Namespaces*. https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/. 2024.
> Official documentation on namespace scoping, DNS behaviour (`<service>.<namespace>.svc.cluster.local`), resource quotas, and when to use multiple namespaces.

@TODO
1. What happens when you deploy to a kubernetes cluster? 
2. What does ImagePullSecret do?
3. What are the kubernetes components that we need to make use of?

---

## AI Tools

*Tools used for code generation, documentation writing, and architecture research throughout this project.*

[26]. GitHub. *GitHub Copilot*. https://github.com/features/copilot. GitHub, Inc. 2025.
> AI coding assistant integrated into VS Code. Used via custom `@engineer` and `@docs` agent definitions
> for code generation, documentation writing, and MLOps research. All AI-generated output was reviewed
> and validated by the developer before use.

[27]. Anthropic. *Claude Sonnet 4.6*. https://www.anthropic.com. Anthropic PBC. 2025.
> Large language model powering GitHub Copilot Chat. Used via the `@engineer` agent for ML pipeline
> code, FastAPI serving layer, CI/CD pipeline design, and AKS deployment configuration.

[28]. Anthropic. *Claude Opus 4.6*. https://www.anthropic.com. Anthropic PBC. 2025.
> Large language model powering GitHub Copilot Chat. Used via the `@docs` agent for documentation
> writing, official source research, and MLOps reference synthesis across `docs/` and `REFERENCES.md`.

[29]. GitHub. *Responsible use of GitHub Copilot Chat in your IDE*. https://docs.github.com/en/copilot/responsible-use/chat-in-your-ide. 2025.
> Official responsible use guidelines followed during this project. Key practices applied: AI as a
> tool not a replacement, human review of all generated content, secure coding practices applied
> to all AI-suggested code.
