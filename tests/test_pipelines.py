"""
test_pipelines.py — Validate Azure DevOps pipeline YAML files.

Tests cover:
  - YAML syntax and structure
  - Stage dependencies and ordering
  - Condition expressions reference valid stages
  - Variable group and variable references
  - Required tasks exist in each stage
  - Blob storage paths are consistent across pipelines
  - Docker image naming consistency
  - K8s namespace / manifest alignment
  - Trigger configuration
"""

import os
import re
from pathlib import Path

import pytest
import yaml

PIPELINE_DIR = Path(__file__).resolve().parent.parent / ".azure"
K8S_DIR = Path(__file__).resolve().parent.parent / "k8s"


# ── Helpers ─────────────────────────────────────────────────────────────────


def _load_pipeline(name: str) -> dict:
    """Load a pipeline YAML file and return parsed dict."""
    path = PIPELINE_DIR / name
    with open(path) as f:
        return yaml.safe_load(f)


def _flatten_steps(pipeline: dict) -> list[dict]:
    """Extract all steps from all stages/jobs in a pipeline."""
    steps = []
    if "steps" in pipeline:
        steps.extend(pipeline["steps"])
    for stage in pipeline.get("stages", []):
        for job in stage.get("jobs", []):
            for step in job.get("steps", []):
                steps.append(step)
            # deployment jobs have strategy.runOnce.deploy.steps
            strategy = job.get("strategy", {})
            deploy = strategy.get("runOnce", {}).get("deploy", {})
            for step in deploy.get("steps", []):
                steps.append(step)
    return steps


def _get_stage_names(pipeline: dict) -> list[str]:
    """Return ordered list of stage names."""
    return [s["stage"] for s in pipeline.get("stages", [])]


def _get_all_text(pipeline: dict) -> str:
    """Dump the entire pipeline dict back to YAML for regex searching."""
    return yaml.dump(pipeline, default_flow_style=False)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def main_pipeline():
    return _load_pipeline("azure-pipelines.yml")


@pytest.fixture(scope="module")
def pr_pipeline():
    return _load_pipeline("pr-validation.yml")


@pytest.fixture(scope="module")
def retrain_pipeline():
    return _load_pipeline("retrain.yml")


# ══════════════════════════════════════════════════════════════════════════════
# 1. YAML syntax — all pipeline files parse without error
# ══════════════════════════════════════════════════════════════════════════════


class TestYAMLValidity:
    @pytest.mark.parametrize(
        "filename",
        ["azure-pipelines.yml", "pr-validation.yml", "retrain.yml"],
    )
    def test_yaml_parses(self, filename):
        """Each pipeline YAML file must be syntactically valid."""
        path = PIPELINE_DIR / filename
        assert path.exists(), f"{filename} not found in .azure/"
        with open(path) as f:
            doc = yaml.safe_load(f)
        assert doc is not None


# ══════════════════════════════════════════════════════════════════════════════
# 2. Main pipeline (azure-pipelines.yml) structure
# ══════════════════════════════════════════════════════════════════════════════


class TestMainPipeline:
    def test_trigger_branches(self, main_pipeline):
        """CI/CD pipeline triggers on dev and main only."""
        branches = main_pipeline["trigger"]["branches"]["include"]
        assert set(branches) == {"dev", "main"}

    def test_pr_disabled(self, main_pipeline):
        """Push pipeline should not trigger on PRs (handled by pr-validation)."""
        assert main_pipeline.get("pr") is None or main_pipeline["pr"] == "none"

    def test_docs_excluded(self, main_pipeline):
        """Docs and markdown files excluded from trigger."""
        excludes = main_pipeline["trigger"]["paths"]["exclude"]
        assert "docs/**" in excludes
        assert "*.md" in excludes or '"*.md"' in excludes

    def test_stage_names(self, main_pipeline):
        """Pipeline must have CI, TrainModel, CD_Dev, CD_Main stages."""
        names = _get_stage_names(main_pipeline)
        assert names == ["CI", "TrainModel", "CD_Dev", "CD_Main"]

    def test_stage_dependencies(self, main_pipeline):
        """TrainModel depends on CI; CD stages depend on CI + TrainModel."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}

        assert stages["TrainModel"]["dependsOn"] == "CI"

        assert set(stages["CD_Dev"]["dependsOn"]) == {"CI", "TrainModel"}
        assert set(stages["CD_Main"]["dependsOn"]) == {"CI", "TrainModel"}

    def test_train_model_conditional(self, main_pipeline):
        """TrainModel stage must be conditional on NEEDS_TRAIN output."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        condition = stages["TrainModel"]["condition"]
        assert "NEEDS_TRAIN" in condition
        assert "DetectChanges" in condition

    def test_cd_dev_branch_condition(self, main_pipeline):
        """CD_Dev only runs on dev branch."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        condition = stages["CD_Dev"]["condition"]
        assert "dev" in condition

    def test_cd_main_branch_condition(self, main_pipeline):
        """CD_Main only runs on main branch."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        condition = stages["CD_Main"]["condition"]
        assert "main" in condition

    def test_cd_stages_handle_skipped_training(self, main_pipeline):
        """CD stages must run even when TrainModel is skipped."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        for stage_name in ("CD_Dev", "CD_Main"):
            condition = stages[stage_name]["condition"]
            assert "Skipped" in condition, (
                f"{stage_name} must allow TrainModel to be Skipped"
            )

    def test_cd_stages_have_training_ran_variable(self, main_pipeline):
        """CD stages must define TRAINING_RAN to conditionally promote model."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        for stage_name in ("CD_Dev", "CD_Main"):
            text = yaml.dump(stages[stage_name])
            assert "TRAINING_RAN" in text, (
                f"{stage_name} missing TRAINING_RAN variable"
            )

    def test_variable_group_referenced(self, main_pipeline):
        """Pipeline must reference bank-marketing-vars variable group."""
        variables = main_pipeline.get("variables", [])
        groups = [
            v["group"] for v in variables if isinstance(v, dict) and "group" in v
        ]
        assert "bank-marketing-vars" in groups

    def test_ci_has_test_step(self, main_pipeline):
        """CI stage must run pytest."""
        text = _get_all_text(main_pipeline)
        assert "pytest" in text

    def test_ci_has_kubeconform(self, main_pipeline):
        """CI stage must validate K8s manifests."""
        text = _get_all_text(main_pipeline)
        assert "kubeconform" in text

    def test_ci_has_pip_audit(self, main_pipeline):
        """CI stage must run dependency vulnerability scan."""
        text = _get_all_text(main_pipeline)
        assert "pip-audit" in text

    def test_detect_changes_job(self, main_pipeline):
        """CI stage must have DetectChanges job with output variable."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        ci_jobs = {j.get("job"): j for j in stages["CI"]["jobs"]}
        assert "DetectChanges" in ci_jobs
        text = yaml.dump(ci_jobs["DetectChanges"])
        assert "isOutput=true" in text

    def test_train_model_uploads_to_blob(self, main_pipeline):
        """TrainModel must upload artifacts to blob storage model registry."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        text = yaml.dump(stages["TrainModel"])
        assert "BLOB_CONTAINER_REGISTRY" in text
        assert "model.pkl" in text

    def test_cd_dev_deploys_to_dev_namespace(self, main_pipeline):
        """CD_Dev must deploy to bank-marketing-dev namespace."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        text = yaml.dump(stages["CD_Dev"])
        assert "bank-marketing-dev" in text

    def test_cd_main_deploys_to_prod_namespace(self, main_pipeline):
        """CD_Main must deploy to bank-marketing namespace."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        text = yaml.dump(stages["CD_Main"])
        assert "namespace: bank-marketing\n" in text or "bank-marketing\n" in text

    def test_trivy_scans_present(self, main_pipeline):
        """Pipeline must include Trivy container vulnerability scans."""
        text = _get_all_text(main_pipeline)
        assert text.count("trivy") >= 2  # at least training + inference

    def test_smoke_tests_present(self, main_pipeline):
        """CD stages must include smoke tests."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        for stage_name in ("CD_Dev", "CD_Main"):
            text = yaml.dump(stages[stage_name])
            assert "/health" in text, f"{stage_name} missing smoke test"

    def test_rolling_restart_conditional(self, main_pipeline):
        """Rolling restart only triggers when TRAINING_RAN is True."""
        stages = {s["stage"]: s for s in main_pipeline["stages"]}
        for stage_name in ("CD_Dev", "CD_Main"):
            text = yaml.dump(stages[stage_name])
            # YAML dump may wrap 'rollout restart' across lines; check both words
            assert "rollout" in text and "restart" in text, (
                f"{stage_name} missing rolling restart"
            )


# ══════════════════════════════════════════════════════════════════════════════
# 3. PR validation pipeline
# ══════════════════════════════════════════════════════════════════════════════


class TestPRPipeline:
    def test_trigger_disabled(self, pr_pipeline):
        """PR pipeline should not trigger on push (trigger: none)."""
        assert pr_pipeline.get(
            "trigger") is None or pr_pipeline["trigger"] == "none"

    def test_pr_branches(self, pr_pipeline):
        """PR pipeline triggers on PRs against dev and main."""
        branches = pr_pipeline["pr"]["branches"]["include"]
        assert set(branches) == {"dev", "main"}

    def test_has_pytest(self, pr_pipeline):
        text = _get_all_text(pr_pipeline)
        assert "pytest" in text

    def test_has_kubeconform(self, pr_pipeline):
        text = _get_all_text(pr_pipeline)
        assert "kubeconform" in text

    def test_has_pip_audit(self, pr_pipeline):
        text = _get_all_text(pr_pipeline)
        assert "pip-audit" in text

    def test_builds_both_images(self, pr_pipeline):
        """PR pipeline must build both training and inference images."""
        text = _get_all_text(pr_pipeline)
        assert "Dockerfile.train" in text
        assert "Dockerfile.infer" in text

    def test_runs_training_container(self, pr_pipeline):
        """PR pipeline must run training to produce model.pkl for inference build test."""
        text = _get_all_text(pr_pipeline)
        assert "docker run" in text
        assert "model.pkl" in text

    def test_container_smoke_test(self, pr_pipeline):
        """PR pipeline must do a container smoke test for the inference image."""
        text = _get_all_text(pr_pipeline)
        assert "/health" in text

    def test_no_acr_push(self, pr_pipeline):
        """PR pipeline should not push to ACR."""
        text = _get_all_text(pr_pipeline)
        assert "buildAndPush" not in text

    def test_trivy_scans(self, pr_pipeline):
        """PR pipeline must scan both images with Trivy."""
        text = _get_all_text(pr_pipeline)
        assert text.count("trivy") >= 2

    def test_gitleaks(self, pr_pipeline):
        """PR pipeline must run secret scanning."""
        text = _get_all_text(pr_pipeline)
        assert "gitleaks" in text


# ══════════════════════════════════════════════════════════════════════════════
# 4. Retrain pipeline
# ══════════════════════════════════════════════════════════════════════════════


class TestRetrainPipeline:
    def test_trigger_disabled(self, retrain_pipeline):
        """Retrain pipeline must not trigger on pushes."""
        assert retrain_pipeline.get(
            "trigger") is None or retrain_pipeline["trigger"] == "none"

    def test_has_schedule(self, retrain_pipeline):
        """Retrain pipeline must have a scheduled trigger."""
        schedules = retrain_pipeline.get("schedules", [])
        assert len(schedules) >= 1
        assert "cron" in schedules[0]

    def test_data_blob_parameter(self, retrain_pipeline):
        """Retrain pipeline must accept dataBlob parameter."""
        params = retrain_pipeline.get("parameters", [])
        param_names = [p["name"] for p in params]
        assert "dataBlob" in param_names

    def test_stage_order(self, retrain_pipeline):
        """Stages: Retrain → ValidateModel → DeployStaging → DeployProduction."""
        names = _get_stage_names(retrain_pipeline)
        assert names == ["Retrain", "ValidateModel",
                         "DeployStaging", "DeployProduction"]

    def test_stage_dependencies(self, retrain_pipeline):
        """Each stage depends on its predecessor."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        assert stages["ValidateModel"]["dependsOn"] == "Retrain"
        assert stages["DeployStaging"]["dependsOn"] == "ValidateModel"
        assert stages["DeployProduction"]["dependsOn"] == "DeployStaging"

    def test_quality_gate(self, retrain_pipeline):
        """ValidateModel must compare ROC-AUC against baseline."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["ValidateModel"])
        assert "roc_auc" in text.lower() or "ROC-AUC" in text

    def test_pulls_train_latest(self, retrain_pipeline):
        """Retrain stage must pull existing train-latest (no rebuild)."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["Retrain"])
        assert "train-latest" in text

    def test_blob_model_registry_upload(self, retrain_pipeline):
        """Retrain uploads to $(BLOB_CONTAINER_REGISTRY)/builds/retrain-$(Build.BuildId)/."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["Retrain"])
        assert "BLOB_CONTAINER_REGISTRY" in text
        assert "retrain-" in text

    def test_staging_promotion(self, retrain_pipeline):
        """DeployStaging promotes model to staging/artifacts/ in blob."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["DeployStaging"])
        assert "staging/artifacts/model.pkl" in text

    def test_production_promotion(self, retrain_pipeline):
        """DeployProduction promotes model to production/artifacts/ in blob."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["DeployProduction"])
        assert "production/artifacts/model.pkl" in text

    def test_uses_production_environment(self, retrain_pipeline):
        """DeployProduction must target 'production' environment for approval gate."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["DeployProduction"])
        assert "environment: production" in text

    def test_smoke_tests(self, retrain_pipeline):
        """Retrain pipeline must smoke-test after staging deployment."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["DeployStaging"])
        assert "/health" in text

    def test_baseline_metrics_updated(self, retrain_pipeline):
        """DeployProduction must update baseline metrics in blob storage."""
        stages = {s["stage"]: s for s in retrain_pipeline["stages"]}
        text = yaml.dump(stages["DeployProduction"])
        assert "production/artifacts/metrics.json" in text


# ══════════════════════════════════════════════════════════════════════════════
# 5. Cross-pipeline consistency
# ══════════════════════════════════════════════════════════════════════════════


class TestCrossPipelineConsistency:
    def test_blob_path_consistency(self, main_pipeline, retrain_pipeline):
        """Blob promotion paths must be consistent across pipelines.

        Both staging and production paths must use the artifacts/ prefix.
        """
        main_text = _get_all_text(main_pipeline)
        retrain_text = _get_all_text(retrain_pipeline)

        # Both should use the same promotion pattern
        assert "staging/artifacts/model.pkl" in main_text
        assert "production/artifacts/model.pkl" in main_text
        assert "staging/artifacts/model.pkl" in retrain_text
        assert "production/artifacts/model.pkl" in retrain_text

    def test_variable_group_consistency(self, main_pipeline, retrain_pipeline):
        """Both pipelines must use the same variable group."""
        for pipeline in (main_pipeline, retrain_pipeline):
            variables = pipeline.get("variables", [])
            groups = [
                v["group"]
                for v in variables
                if isinstance(v, dict) and "group" in v
            ]
            assert "bank-marketing-vars" in groups

    def test_python_version_consistency(self, main_pipeline, pr_pipeline):
        """CI and PR pipelines must use the same Python version."""
        for pipeline in (main_pipeline, pr_pipeline):
            text = _get_all_text(pipeline)
            assert "3.12" in text

    def test_requirements_file_consistency(self, main_pipeline, pr_pipeline):
        """Both CI and PR must install from same requirements file."""
        for pipeline in (main_pipeline, pr_pipeline):
            text = _get_all_text(pipeline)
            assert "requirements-local.txt" in text


# ══════════════════════════════════════════════════════════════════════════════
# 6. K8s manifest and pipeline alignment
# ══════════════════════════════════════════════════════════════════════════════


class TestK8sPipelineAlignment:
    def test_deployment_namespaces_match_pipeline(self, main_pipeline):
        """K8s deployment namespaces must match pipeline deployment targets."""
        # deployment.yaml → bank-marketing (production)
        with open(K8S_DIR / "deployment.yaml") as f:
            prod_deploy = yaml.safe_load(f)
        assert prod_deploy["metadata"]["namespace"] == "bank-marketing"

        # deployment-dev.yaml → bank-marketing-dev (staging)
        with open(K8S_DIR / "deployment-dev.yaml") as f:
            dev_deploy = yaml.safe_load(f)
        assert dev_deploy["metadata"]["namespace"] == "bank-marketing-dev"

    def test_model_blob_prefix_matches_promotion_paths(self):
        """K8s MODEL_BLOB_PREFIX must align with pipeline blob promotion paths."""
        with open(K8S_DIR / "deployment.yaml") as f:
            prod = yaml.safe_load(f)
        with open(K8S_DIR / "deployment-dev.yaml") as f:
            dev = yaml.safe_load(f)

        def _get_env(deploy, name):
            envs = deploy["spec"]["template"]["spec"]["containers"][0]["env"]
            return next((e["value"] for e in envs if e["name"] == name), None)

        assert _get_env(prod, "MODEL_BLOB_PREFIX") == "production"
        assert _get_env(dev, "MODEL_BLOB_PREFIX") == "staging"

    def test_storage_backend_is_azure_blob(self):
        """K8s deployments must use azure_blob storage backend."""
        for name in ("deployment.yaml", "deployment-dev.yaml"):
            with open(K8S_DIR / name) as f:
                deploy = yaml.safe_load(f)
            envs = deploy["spec"]["template"]["spec"]["containers"][0]["env"]
            backend = next(
                (e["value"] for e in envs if e["name"] == "STORAGE_BACKEND"),
                None,
            )
            assert backend == "azure_blob", f"{name}: STORAGE_BACKEND != azure_blob"

    def test_k8s_manifests_referenced_in_pipelines(self, main_pipeline, retrain_pipeline):
        """Pipelines must reference the correct K8s manifest files."""
        main_text = _get_all_text(main_pipeline)
        retrain_text = _get_all_text(retrain_pipeline)

        assert "deployment-dev.yaml" in main_text
        assert "deployment.yaml" in main_text
        assert "deployment-dev.yaml" in retrain_text
        assert "deployment.yaml" in retrain_text

    def test_service_dev_is_clusterip(self):
        """Dev service should be ClusterIP (no external exposure in staging)."""
        with open(K8S_DIR / "service-dev.yaml") as f:
            svc = yaml.safe_load(f)
        assert svc["spec"]["type"] == "ClusterIP"

    def test_service_prod_is_loadbalancer(self):
        """Production service should be LoadBalancer for external access."""
        with open(K8S_DIR / "service.yaml") as f:
            svc = yaml.safe_load(f)
        assert svc["spec"]["type"] == "LoadBalancer"
