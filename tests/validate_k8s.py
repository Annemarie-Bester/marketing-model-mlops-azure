"""Offline K8s manifest validation (structural checks)."""
import os
import sys

import yaml


def validate_manifests():
    errors = []
    k8s_dir = os.path.join(os.path.dirname(__file__), "..", "k8s")

    for f in sorted(os.listdir(k8s_dir)):
        if not f.endswith(".yaml"):
            continue
        path = os.path.join(k8s_dir, f)
        with open(path) as fh:
            docs = list(yaml.safe_load_all(fh))
        for doc in docs:
            if not doc:
                continue
            kind = doc.get("kind", "MISSING")
            api = doc.get("apiVersion", "MISSING")
            name = doc.get("metadata", {}).get("name", "MISSING")
            ns = doc.get("metadata", {}).get("namespace", "N/A")
            print(f"  OK {f}: {kind}/{name} (ns={ns}, api={api})")

            if kind == "MISSING":
                errors.append(f"{f}: missing kind")
            if api == "MISSING":
                errors.append(f"{f}: missing apiVersion")
            if name == "MISSING":
                errors.append(f"{f}: missing metadata.name")

            if kind == "Deployment":
                spec = doc.get("spec", {})
                template = spec.get("template", {})
                containers = template.get("spec", {}).get("containers", [])
                if not containers:
                    errors.append(f"{f}: no containers")
                for c in containers:
                    cname = c.get("name", "?")
                    if "resources" not in c:
                        errors.append(
                            f"{f}: container '{cname}' missing resources")
                    if "livenessProbe" not in c:
                        errors.append(
                            f"{f}: container '{cname}' missing livenessProbe")
                    if "readinessProbe" not in c:
                        errors.append(
                            f"{f}: container '{cname}' missing readinessProbe")
                    envs = [e["name"] for e in c.get("env", [])]
                    print(f"    env: {envs}")

            if kind == "Service":
                svc_spec = doc.get("spec", {})
                svc_type = svc_spec.get("type", "ClusterIP")
                ports = [(p.get("port"), p.get("targetPort"))
                         for p in svc_spec.get("ports", [])]
                print(f"    type={svc_type}, ports={ports}")

    print()
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  FAIL {e}")
        return 1
    print("All K8s manifests structurally valid")
    return 0


if __name__ == "__main__":
    sys.exit(validate_manifests())
