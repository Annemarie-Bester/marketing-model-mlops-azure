# References

Bibliography for the Bank Marketing MLOps project, organised by topic.

**Format:** `[N]. Author(s) or Organisation. *Title*. Publisher / URL. Year.`
Leave a `> Note:` line beneath an entry to record why it was useful.

> Reference numbers follow section order — ML modelling sections are numbered first ([1]–[7]), followed by MLOps lifecycle ([8]–[10]), CI/CD ([11]–[28]), Azure infrastructure ([29]–[37]), deployment strategies ([38]–[41]), and AI tools ([42]–[45]). Cross-references in `docs/` use the bracket notation to link back here.

---

## Table of Contents

1. [ML Pipeline & Preprocessing](#ml-pipeline--preprocessing)
2. [Classification Models](#classification-models)
3. [Model Evaluation & Metrics](#model-evaluation--metrics)
4. [Model Serialisation & Artifact Management](#model-serialisation--artifact-management)
5. [MLOps Lifecycle & Maturity](#mlops-lifecycle--maturity)
6. [CI/CD Pipelines — Azure DevOps + AKS](#cicd-pipelines--azure-devops--aks)
7. [Azure Infrastructure & Platform](#azure-infrastructure--platform)
8. [Cluster Isolation & Deployment Strategies](#cluster-isolation--deployment-strategies)
9. [AI Tools](#ai-tools)

---

## ML Pipeline & Preprocessing

*Topics: sklearn Pipeline, ColumnTransformer, SimpleImputer, StandardScaler, OneHotEncoder, stratified splitting, feature engineering.*

[1]. scikit-learn. *User Guide — Pipelines and composite estimators*. https://scikit-learn.org/stable/modules/compose.html. 2024.
> Comprehensive guide to `sklearn.pipeline.Pipeline` and `ColumnTransformer` — explains how wrapping preprocessor and classifier in a single Pipeline prevents data leakage and produces a self-contained artifact. The design rationale behind `build_preprocessor()` and `train()` in this project.

[2]. scikit-learn. *Column Transformer with Mixed Types — Official Example*. https://scikit-learn.org/stable/auto_examples/compose/plot_column_transformer_mixed_types.html. 2024.
> Official sklearn example showing a `ColumnTransformer` with separate sub-pipelines for numeric features (`SimpleImputer` + `StandardScaler`) and categorical features (`OneHotEncoder`) — the exact pattern implemented in `build_preprocessor()` in `src/features.py`.

[3]. scikit-learn. *scikit-learn/scikit-learn — Official examples (GitHub)*. https://github.com/scikit-learn/scikit-learn/tree/main/examples. GitHub, 2024.
> Official sklearn examples repository — the `compose/` directory covers `ColumnTransformer` and `Pipeline` construction patterns; the `classification/` directory covers classifier comparison and evaluation approaches. Concrete, runnable code complementing the user guide sections.

---

## Classification Models

*Topics: Logistic Regression (lbfgs, class_weight), Gradient Boosting (residual learning, imbalance), Random Forest (bagging, class_weight), solver selection, hyperparameter defaults.*

[4]. scikit-learn. *User Guide — Logistic Regression*. https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression. 2024.
> Official guide for `LogisticRegression` — covers solver selection (`lbfgs` for small-to-medium datasets), `max_iter` tuning, and `class_weight='balanced'` for adjusting decision boundaries under class imbalance. The interpretable baseline model selected as the project default in `config.yaml`.

[5]. scikit-learn. *User Guide — Ensemble methods*. https://scikit-learn.org/stable/modules/ensemble.html. 2024.
> Official reference for `GradientBoostingClassifier` and `RandomForestClassifier` — covers `n_estimators`, `max_depth`, `learning_rate`, feature importance, and `class_weight` support. GradientBoosting handles imbalance through sequential residual fitting; RandomForest uses `class_weight='balanced'`. Foundation for the `MODEL_REGISTRY` entries in `src/train.py`.

---

## Model Evaluation & Metrics

*Topics: ROC-AUC, F1-score (binary, macro), classification report, why accuracy is misleading for imbalanced data, threshold selection.*

[6]. scikit-learn. *User Guide — Model evaluation: quantifying the quality of predictions*. https://scikit-learn.org/stable/modules/model_evaluation.html. 2024.
> Comprehensive official guide covering `roc_auc_score`, `f1_score`, `classification_report`, and the section on why accuracy is a misleading metric for class-imbalanced problems. The evaluation strategy in `src/evaluate.py` — choosing ROC-AUC and minority-class F1 over accuracy, with a 7.6:1 class imbalance — follows this guidance directly.

---

## Model Serialisation & Artifact Management

*Topics: joblib serialisation, Pipeline persistence, artifact reproducibility, version compatibility.*

[7]. scikit-learn. *Model persistence*. https://scikit-learn.org/stable/model_persistence.html. 2024.
> Official guide for serialising and loading `sklearn.pipeline.Pipeline` objects using `joblib.dump` / `joblib.load` — covers best practices, security considerations, and Python/sklearn version compatibility. The foundation for `artifacts/model.pkl` in this project.

---

## MLOps Lifecycle & Maturity

*Topics: inner loop → outer loop model lifecycle, MLOps maturity levels, CI/CD-driven model deployment.*

[8]. Microsoft. *Machine learning operations (MLOps v2)*. https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/machine-learning-operations-v2. 2024.
> Canonical Azure MLOps reference — inner loop (model development) → outer loop (model deployment) lifecycle with CI/CD pipelines promoting models through staging → production on AKS.

[9]. Microsoft. *MLOps maturity model*. https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model. 2025.
> Five maturity levels (0–4) for assessing MLOps capability. Useful for framing current state and target state.

[10]. Microsoft. *MLOps and GenAIOps for AI workloads*. https://learn.microsoft.com/en-us/azure/well-architected/ai/mlops-genaiops. 2024.
> Azure Well-Architected Framework perspective on why ML workloads need specialised operations.

---

## CI/CD Pipelines — Azure DevOps + AKS

*Topics: Azure DevOps Pipelines, multi-stage YAML, PR validation, branch policies, ACR push, KubernetesManifest task, AzureML endpoint patterns.*

[11]. Microsoft. *Build and deploy to Azure Kubernetes Service with Azure Pipelines*. https://learn.microsoft.com/en-us/azure/aks/devops-pipeline. 2025.
> Step-by-step walkthrough: create ACR, AKS cluster, and a two-stage Azure DevOps pipeline (Build → Deploy) with Docker@2 and KubernetesManifest@1 tasks.

[12]. Microsoft. *Build a CI/CD pipeline for microservices on Kubernetes with Azure DevOps and Helm*. https://learn.microsoft.com/en-us/azure/architecture/microservices/ci-cd-kubernetes. 2024.
> Architecture-level guide covering validation builds, full CI/CD flow, Helm chart packaging, environment isolation, and container best practices.

[13]. Microsoft. *Azure MLOps v2 — GitHub repository*. https://github.com/Azure/mlops-v2. 2024.
> Deployable sample templates for the MLOps v2 architecture, including CI/CD pipeline definitions for classical ML scenarios.

[14]. Microsoft/Azure. *AzureML Examples — Kubernetes Online Endpoint Simple Deployment*. https://github.com/Azure/azureml-examples/blob/main/sdk/python/endpoints/online/kubernetes/kubernetes-online-endpoints-simple-deployment.ipynb. GitHub, 2024.
> End-to-end SDK example: create a Kubernetes online endpoint, configure a custom container deployment, and validate predictions — reference for understanding the full AzureML endpoint lifecycle on AKS.

[15]. Microsoft/Azure. *AzureML Examples — Setup Scripts*. https://github.com/Azure/azureml-examples/tree/main/setup. GitHub, 2024.
> Infrastructure setup scripts for the AzureML examples repository — compute cluster and workspace provisioning patterns referenced during cluster and workspace setup research.

[16]. Microsoft/Azure. *AzureML Examples — CLI Kubernetes Online Endpoints*. https://github.com/Azure/azureml-examples/tree/main/cli/endpoints/online/kubernetes. GitHub, 2024.
> CLI-based deployment examples for Kubernetes online endpoints — covers `endpoint.yml` and `deployment.yml` patterns for registering custom containers as AzureML online endpoints.

[17]. Microsoft. *Online Endpoints — Managed vs Kubernetes Online Endpoints*. https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#managed-online-endpoints-vs-kubernetes-online-endpoints. 2024.
> Compares Azure-managed online endpoints with customer-managed Kubernetes online endpoints — informed the architectural decision to use direct AKS deployment over AzureML managed endpoints for this project.

[18]. Microsoft. *Deploy a custom container to an Azure Machine Learning online endpoint*. https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-custom-container?view=azureml-api-2&tabs=cli. 2024.
> Step-by-step guide for packaging a custom Docker container and registering it as an AzureML online endpoint — covers container specs, scoring scripts, and environment configuration.

[19]. Microsoft. *Online Endpoints — Local Debugging with Local Endpoint*. https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#local-debugging-with-local-endpoint. 2024.
> Describes how to test a container image locally before pushing to AKS — local endpoint debugging pattern used to validate the model container before CI/CD deployment.

[20]. Microsoft. *Create your first pipeline — Azure DevOps*. https://learn.microsoft.com/en-us/azure/devops/pipelines/create-first-pipeline?view=azure-devops&tabs=python%2Cbrowser. 2025.
> Official Azure Pipelines quickstart: connect a repository, create a YAML pipeline, configure triggers, and understand pipeline stages — foundational reference for the project's `azure-pipelines.yml` structure.

[21]. Microsoft. *Deploy a machine learning model to Azure Kubernetes Service (v1)*. https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-azure-kubernetes-service?view=azureml-api-1&tabs=python. 2024.
> AzureML SDK v1 reference for deploying registered models to AKS — covers inference configuration, deployment configuration, and health probe setup on AKS clusters.

[22]. Microsoft/Azure. *MLOps v2 — Classical ML Architecture Diagram*. https://github.com/Azure/mlops-v2/blob/main/documentation/architecture/media/AzureML_CML_Architecture.png. GitHub, 2024.
> Visual reference for the AzureML MLOps v2 classical ML architecture — shows the relationship between CI/CD pipelines, model registry, and AKS serving; used as the architectural benchmark for this project's GitHub → ADO → ACR → AKS design.

[23]. Microsoft/Azure. *MLOps v2 — Azure DevOps Deployment Guide*. https://github.com/Azure/mlops-v2/blob/main/documentation/deployguides/deployguide_ado.md. GitHub, 2024.
> Step-by-step deployment guide for provisioning the MLOps v2 infrastructure using Azure DevOps — covers service connections, variable groups, and multi-stage pipeline structure for ACR → AKS deployment.

[24]. Microsoft. *Quickstart: Create an Azure Container Registry using Terraform*. https://learn.microsoft.com/en-us/azure/container-registry/container-registry-get-started-terraform?tabs=azure-cli. 2024.
> Terraform-based ACR provisioning reference — covers registry SKU selection, admin user configuration, and AKS integration via `imagePullSecrets`; referenced when researching ACR setup options.

[25]. Microsoft. *Build GitHub repositories — Azure Pipelines*. https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/github?view=azure-devops&tabs=yaml. 2025.
> Comprehensive reference for connecting GitHub repos to Azure Pipelines — covers service connections, webhook installation, `pr:` and `trigger:` YAML syntax, and branch filters that control which branches trigger CI/CD builds.

[26]. Microsoft. *Pipeline conditions — Azure DevOps Pipelines*. https://learn.microsoft.com/en-us/azure/devops/pipelines/process/conditions. 2025.
> Runtime expression syntax (`$[ ]`) and `Build.SourceBranch` variable used to gate branch-conditional CD stages — the mechanism that makes `CD_Dev` and `CD_Main` mutually exclusive in `azure-pipelines.yml`.

[27]. Microsoft. *YAML templates in Azure Pipelines*. https://learn.microsoft.com/en-us/azure/devops/pipelines/process/templates. 2025.
> Parameterised template includes and `${{ if }}` expressions — an alternative DRY approach for shared CI stage logic; considered but not implemented in favour of explicit stage definitions for clarity.

[28]. Microsoft. *Build Azure Repos Git repositories — PR triggers*. https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/azure-repos-git#pr-triggers. 2025.
> Documents that the `pr:` YAML keyword is not supported for Azure Repos Git — PR validation must be configured via Branch Policies instead. Critical distinction for understanding why Pipeline 1 uses Branch Policy configuration rather than YAML triggers.

---

## Azure Infrastructure & Platform

*Topics: AKS core concepts, ACR setup and authentication, Azure Monitor, Azure Pipelines platform overview, GitOps.*

[29]. Microsoft. *Core concepts for Azure Kubernetes Service (AKS)*. https://learn.microsoft.com/en-us/azure/aks/concepts-clusters-workloads. 2025.
> Foundational reference for AKS clusters, node pools, pods, namespaces, and pricing tiers.

[30]. Microsoft. *What is Azure Pipelines?*. https://learn.microsoft.com/en-us/azure/devops/pipelines/get-started/what-is-azure-pipelines. 2024.
> Official Azure Pipelines entry point — build/release pipelines, YAML syntax, service connections, and environments.

[31]. Microsoft. *Introduction to Container registries in Azure*. https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro. 2024.
> ACR creation, repository namespaces, image tagging strategies, and Helm chart storage.

[32]. Microsoft. *End-to-end MLOps with Azure Machine Learning (Learning Path)*. https://learn.microsoft.com/en-us/training/paths/build-first-machine-operations-workflow. 2024.
> Hands-on training path for building a first MLOps workflow.

[33]. Microsoft. *GitOps for Azure Kubernetes Service*. https://learn.microsoft.com/en-us/azure/architecture/example-scenario/gitops-aks/gitops-blueprint-aks. 2024.
> Alternative pull-based deployment model using Flux/ArgoCD — worth considering for production maturity.

[34]. Microsoft. *Azure Kubernetes Service (AKS) documentation*. https://learn.microsoft.com/en-us/azure/aks/. 2025.
> Core reference hub for AKS — cluster creation, networking, node pools, scaling, and monitoring. Entry point for all AKS concepts used in the deployment architecture.

[35]. Microsoft. *Azure Container Registry documentation*. https://learn.microsoft.com/en-us/azure/container-registry/. 2025.
> Core reference hub for ACR — registry creation, authentication, image tagging strategies, and tier comparison. Entry point for all ACR concepts used in the CI/CD pipeline.

[36]. Microsoft. *Authenticate with Azure Container Registry from Azure Kubernetes Service (AKS)*. https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration. 2025.
> Documents the `--attach-acr` integration method that grants AKS the `AcrPull` role on ACR via managed identity — the mechanism used in this project to eliminate `imagePullSecrets`.

[37]. Microsoft. *Azure Monitor container insights overview*. https://learn.microsoft.com/en-us/azure/azure-monitor/containers/container-insights-overview. 2025.
> AKS monitoring addon configuration, metrics collected (CPU, memory, pod health), and log query reference — the observability backend for the deployed prediction service.

---

## Cluster Isolation & Deployment Strategies

*Topics: namespace-based isolation, ephemeral PR environments (Review Apps), blue-green deployment, zero-downtime rollout.*

[38]. Microsoft. *Best practices for cluster isolation in Azure Kubernetes Service (AKS)*. https://learn.microsoft.com/en-us/azure/aks/operator-best-practices-cluster-isolation. 2024.
> Logical (namespace) vs. physical (multi-cluster) isolation patterns. Recommends namespace-based isolation for dev/test environments within a shared cluster to minimise cost and management overhead.

[39]. Microsoft. *Kubernetes resources in environments*. https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments-kubernetes. 2025.
> Azure DevOps Review Apps — deploy every PR to a dynamic ephemeral namespace. Includes complete YAML pipeline example with `DeployPullRequest` jobs, dynamic namespace creation, and PR comment automation.

[40]. Kubernetes. *Namespaces*. https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/. 2024.
> Official documentation on namespace scoping, DNS behaviour (`<service>.<namespace>.svc.cluster.local`), resource quotas, and when to use multiple namespaces.

[41]. Kubernetes. *Zero-downtime Deployment in Kubernetes with Jenkins (blog)*. https://kubernetes.io/blog/2018/04/30/zero-downtime-deployment-kubernetes-jenkins/. 2018.
> Documents the blue/green selector-switching pattern on Kubernetes, including both `Deployment` definitions, the public `Service`, and a separate test `Service` for pre-cutover validation — the reference for the blue-green deployment strategy described in `docs/future-enhancements.md`.

---

## AI Tools

*Tools used for code generation, documentation writing, and architecture research throughout this project.*

[42]. GitHub. *GitHub Copilot*. https://github.com/features/copilot. GitHub, Inc. 2025.
> AI coding assistant integrated into VS Code. Used via custom `@engineer` and `@docs` agent definitions
> for code generation, documentation writing, and MLOps research. All AI-generated output was reviewed
> and validated by the developer before use.

[43]. Anthropic. *Claude Sonnet 4.6*. https://www.anthropic.com. Anthropic PBC. 2025.
> Large language model powering GitHub Copilot Chat. Used via the `@engineer` agent for ML pipeline
> code, FastAPI serving layer, CI/CD pipeline design, and AKS deployment configuration.

[44]. Anthropic. *Claude Opus 4.6*. https://www.anthropic.com. Anthropic PBC. 2025.
> Large language model powering GitHub Copilot Chat. Used via the `@docs` agent for documentation
> writing, official source research, and MLOps reference synthesis across `docs/` and `REFERENCES.md`.

[45]. GitHub. *Responsible use of GitHub Copilot Chat in your IDE*. https://docs.github.com/en/copilot/responsible-use/chat-in-your-ide. 2025.
> Official responsible use guidelines followed during this project. Key practices applied: AI as a
> tool not a replacement, human review of all generated content, secure coding practices applied
> to all AI-suggested code.
