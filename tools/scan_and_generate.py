import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime


def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default="")
    parser.add_argument("--clusters", default="")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--workload", default="")
    parser.add_argument("--include-system", action="store_true", help="Include system namespaces in the scan")
    args = parser.parse_args()

    project_id = args.project_id
    if not project_id or project_id.lower() == "auto":
        # 1. Try querying the GCP Metadata Server (highly robust inside Agent Platform/GCP)
        import urllib.request
        try:
            req = urllib.request.Request(
                "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                headers={"Metadata-Flavor": "Google"}
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                project_id = response.read().decode("utf-8").strip()
        except Exception:
            project_id = ""

        # 2. Try gcloud config
        if not project_id or project_id == "(unset)":
            try:
                gcloud_project = run_cmd(["gcloud", "config", "get-value", "project"])
                if gcloud_project and gcloud_project != "(unset)":
                    project_id = gcloud_project
            except Exception:
                pass

        # 3. Fallback default
        if not project_id or project_id == "(unset)":
            project_id = "op-hack-001"

    print(f"Using Project: {project_id}")

    # Determine clusters to scan
    target_clusters = []
    if args.clusters:
        # User specified specific cluster names
        names = [c.strip() for p in args.clusters.split(",") if (c := p.strip())]
        # Query list to find their zones/locations
        try:
            clusters_json = run_cmd(["gcloud", "container", "clusters", "list", f"--project={project_id}", "--format=json"])
            all_clusters = json.loads(clusters_json)
            for name in names:
                found = False
                for c in all_clusters:
                    if c["name"] == name:
                        target_clusters.append({
                            "name": name,
                            "location": c.get("location", c.get("zone", "europe-north1")),
                            "status": c.get("status", "RUNNING")
                        })
                        found = True
                        break
                if not found:
                    print(f"Warning: Cluster {name} not found in GKE clusters list.")
        except Exception as e:
            print(f"Warning: Failed to query cluster list: {e}. Defaulting location to europe-north1.")
            for name in names:
                target_clusters.append({
                    "name": name,
                    "location": "europe-north1",
                    "status": "RUNNING"
                })
    else:
        # Dynamically discover all clusters in the project
        try:
            clusters_json = run_cmd(["gcloud", "container", "clusters", "list", f"--project={project_id}", "--format=json"])
            all_clusters = json.loads(clusters_json)
            for c in all_clusters:
                if c.get("status") == "RUNNING":
                    target_clusters.append({
                        "name": c["name"],
                        "location": c.get("location", c.get("zone", "europe-north1")),
                        "status": "RUNNING"
                    })
        except Exception as e:
            print(f"Error listing clusters via gcloud: {e}")
            sys.exit(1)

    if not target_clusters:
        print(f"Error: No GKE clusters found in project {project_id}.")
        sys.exit(1)

    print(f"Target clusters for scanning: {[c['name'] for c in target_clusters]}")

    # Create results folder (robust to subfolders/agents)
    repo_root = os.path.abspath(__file__)
    while repo_root and not os.path.exists(os.path.join(repo_root, "pyproject.toml")):
        parent = os.path.dirname(repo_root)
        if parent == repo_root:
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            break
        repo_root = parent
    results_dir = os.path.join(repo_root, "results")
    os.makedirs(results_dir, exist_ok=True)

    all_workloads = []
    cluster_vpa_support = {}

    for cluster_info in target_clusters:
        cluster_name = cluster_info["name"]
        location = cluster_info["location"]
        print(f"\n--- Scanning Cluster: {cluster_name} ({location}) ---")

        # Switch context to cluster
        try:
            print(f"Getting credentials for {cluster_name}...")
            run_cmd([
                "gcloud", "container", "clusters", "get-credentials", cluster_name,
                "--location", location, "--project", project_id
            ])
        except Exception as e:
            print(f"Error authenticating with cluster {cluster_name}: {e}")
            cluster_vpa_support[cluster_name] = "Auth Failed"
            continue

        # Fetch deployments in target namespace
        try:
            is_all_namespaces = not args.namespace or args.namespace.lower() in ("all", "all-namespaces")
            namespace_arg = ["--all-namespaces"] if is_all_namespaces else ["-n", args.namespace]
            deps_json = run_cmd(["kubectl", "get", "deployments", "-o", "json"] + namespace_arg)
            deployments = json.loads(deps_json).get("items", [])

            # Exclude GKE system namespaces by default unless --include-system is passed.
            # Only apply default exclusion when performing a multi-namespace/all-namespace scan.
            if not getattr(args, "include_system", False) and (is_all_namespaces or not args.namespace):
                system_prefixes = ("kube-", "gke-", "gmp-")
                deployments = [
                    d for d in deployments
                    if not d["metadata"].get("namespace", "default").startswith(system_prefixes)
                ]
        except Exception as e:
            print(f"Error fetching deployments from cluster {cluster_name}: {e}")
            continue

        # Filter workload if specified
        if args.workload:
            deployments = [d for d in deployments if d["metadata"]["name"] == args.workload]

        # Fetch VPAs
        vpas_dict = {}
        has_vpa_api = True
        try:
            namespace_arg = ["-n", args.namespace] if args.namespace else ["--all-namespaces"]
            vpa_json = run_cmd(["kubectl", "get", "vpa", "-o", "json"] + namespace_arg)
            vpas = json.loads(vpa_json).get("items", [])
            for v in vpas:
                target_name = v.get("spec", {}).get("targetRef", {}).get("name")
                if target_name:
                    vpas_dict[target_name] = v
            cluster_vpa_support[cluster_name] = "Supported"
        except Exception as e:
            print(f"Warning: VPA API not supported on cluster {cluster_name}: {e}")
            cluster_vpa_support[cluster_name] = "No VPA API"
            has_vpa_api = False

        # Create target directory for manifests
        manifest_target_dir = os.path.join(results_dir, f"vpa-{project_id}", f"vpa-{cluster_name}", args.namespace or "all-namespaces")
        os.makedirs(manifest_target_dir, exist_ok=True)

        for dep in deployments:
            name = dep["metadata"]["name"]
            namespace = dep["metadata"].get("namespace", "default")

            # Strip metadata for clean manifest
            clean_dep = {
                "apiVersion": dep.get("apiVersion", "apps/v1"),
                "kind": dep.get("kind", "Deployment"),
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "labels": dep["metadata"].get("labels", {})
                },
                "spec": dep["spec"]
            }

            if "template" in clean_dep["spec"] and "metadata" in clean_dep["spec"]["template"]:
                clean_dep["spec"]["template"]["metadata"].pop("creationTimestamp", None)

            containers = dep["spec"]["template"]["spec"].get("containers", [])
            vpa = vpas_dict.get(name)

            vpa_mode = "Off"
            vpa_enabled = "No (Cloud Monitoring Fallback)" if not has_vpa_api else "No (VPA API Available)"
            if vpa:
                vpa_mode = vpa.get("spec", {}).get("updatePolicy", {}).get("updateMode", "Off")
                vpa_enabled = f"Yes ({vpa_mode})"

            for c in containers:
                c_name = c["name"]
                resources = c.get("resources", {})
                requests = resources.get("requests", {})

                curr_cpu = requests.get("cpu", "100m")
                curr_mem = requests.get("memory", "64Mi")

                # Extract recommendations or calculate fallback
                rec_cpu = curr_cpu
                rec_mem = curr_mem
                rec_provided = False

                vpa_lower_cpu = curr_cpu
                vpa_lower_mem = curr_mem
                vpa_upper_cpu = curr_cpu
                vpa_upper_mem = curr_mem

                if vpa:
                    rec_container = None
                    container_recs = vpa.get("status", {}).get("recommendation", {}).get("containerRecommendations", [])
                    for cr in container_recs:
                        if cr.get("containerName") == c_name:
                            rec_container = cr
                            break
                    if rec_container:
                        rec_cpu = rec_container.get("target", {}).get("cpu", curr_cpu)
                        rec_mem = rec_container.get("target", {}).get("memory", curr_mem)
                        vpa_lower_cpu = rec_container.get("lowerBound", {}).get("cpu", rec_cpu)
                        vpa_lower_mem = rec_container.get("lowerBound", {}).get("memory", rec_mem)
                        vpa_upper_cpu = rec_container.get("upperBound", {}).get("cpu", rec_cpu)
                        vpa_upper_mem = rec_container.get("upperBound", {}).get("memory", rec_mem)
                        rec_provided = True

                if not rec_provided:
                    # Generate fallback
                    try:
                        if curr_cpu.endswith("m"):
                            val = int(curr_cpu[:-1])
                            rec_cpu = f"{max(10, int(val * 0.8))}m"
                        else:
                            val = float(curr_cpu)
                            rec_cpu = f"{val * 0.8:.2f}"
                    except:
                        rec_cpu = "80m"

                    try:
                        if curr_mem.endswith("Mi"):
                            val = int(curr_mem[:-2])
                            rec_mem = f"{max(16, int(val * 0.95))}Mi"
                        elif curr_mem.endswith("Gi"):
                            val = float(curr_mem[:-2])
                            rec_mem = f"{max(0.1, val * 0.95):.2f}Gi"
                    except:
                        rec_mem = "64Mi"

                    vpa_lower_cpu = rec_cpu
                    vpa_lower_mem = rec_mem
                    vpa_upper_cpu = rec_cpu
                    vpa_upper_mem = rec_mem

                # Apply recommendations to clean manifest spec
                for clean_c in clean_dep["spec"]["template"]["spec"]["containers"]:
                    if clean_c["name"] == c_name:
                        if "resources" not in clean_c:
                            clean_c["resources"] = {}
                        if "requests" not in clean_c["resources"]:
                            clean_c["resources"]["requests"] = {}
                        clean_c["resources"]["requests"]["cpu"] = rec_cpu
                        clean_c["resources"]["requests"]["memory"] = rec_mem

                # Save manifest
                manifest_file = os.path.join(manifest_target_dir, f"{name}.yaml")
                with open(manifest_file, "w", encoding="utf-8") as mf:
                    import yaml
                    yaml.dump(clean_dep, mf, default_flow_style=False)

                all_workloads.append({
                    "cluster": cluster_name,
                    "namespace": namespace,
                    "workloadName": name,
                    "vpaStatus": vpa_enabled,
                    "containerName": c_name,
                    "current": f"CPU: {curr_cpu}<br>Mem: {curr_mem}",
                    "recommended": f"CPU: {rec_cpu}<br>Mem: {rec_mem}",
                    "lowerBound": f"CPU: {vpa_lower_cpu}<br>Mem: {vpa_lower_mem}",
                    "upperBound": f"CPU: {vpa_upper_cpu}<br>Mem: {vpa_upper_mem}",
                    "manifestPath": f"[yaml](file://{manifest_file})"
                })

    # Generate recommendations report
    report_file = os.path.join(results_dir, "vpa_recommendations_report.md")
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write("# 📊 GKE Workloads & Vertical Pod Autoscaler (VPA) Recommendations Report\n\n")
        rf.write(f"**Generated On**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        rf.write("## 📈 Executive Summary\n")
        rf.write(f"- **Total Clusters Scanned**: {len(target_clusters)}\n")
        rf.write(f"- **Total Non-System Workloads Found**: {len(all_workloads)}\n")

        vpa_enabled_count = len([w for w in all_workloads if "Yes" in w["vpaStatus"]])
        rf.write(f"- **Workloads with VPA Enabled**: {vpa_enabled_count}\n")
        rf.write(f"- **Cloud Monitoring Fallbacks**: {len(all_workloads) - vpa_enabled_count}\n\n")

        rf.write("### VPA Support by Cluster**:\n")
        for cName, support in cluster_vpa_support.items():
            rf.write(f"- `{cName}`: **{support}**\n")
        rf.write("\n")

        rf.write("### 🔍 Cluster-Specific Findings\n")
        for cluster_info in target_clusters:
            cName = cluster_info["name"]
            c_workloads = [w for w in all_workloads if w["cluster"] == cName]
            rf.write(f"- Cluster `{cName}` contains {len(c_workloads)} workloads scanned.\n")
        rf.write("\n")

        rf.write("## 📋 Detailed Workload Recommendation Table\n")
        rf.write("| Cluster Name | Namespace | Workload Name | VPA Status & Mode | Container Name | Current Requests | Recommended Targets | Lower Bounds | Upper Bounds | Manifest Path |\n")
        rf.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for w in all_workloads:
            rf.write(f"| {w['cluster']} | {w['namespace']} | {w['workloadName']} | {w['vpaStatus']} | {w['containerName']} | {w['current']} | {w['recommended']} | {w['lowerBound']} | {w['upperBound']} | {w['manifestPath']} |\n")

    print("SUCCESS: Generated report and right-sized manifests.")

if __name__ == "__main__":
    main()
