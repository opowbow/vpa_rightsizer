import os
import subprocess


def run_project_vpa_scan(
    project_id: str = "",
    cluster_filter: str = "",
    namespace_filter: str = "default",
    workload_filter: str = "",
    include_system: bool = False
) -> str:
    """
    Executes a project-wide GKE cluster resource scan across GKE clusters
    (fetching active Kubernetes VPA recommendations and Cloud Monitoring fallback metrics).
    
    Args:
        project_id: The Google Cloud project ID. If empty, auto-discovers active config.
        cluster_filter: Optional comma-separated list of specific cluster names.
        namespace_filter: Kubernetes namespace to scan (default: "default").
        workload_filter: Specific workload name to target.
        include_system: If True, GKE system namespaces (kube-, gke-, gmp-) are included in the scan.
        
    Returns:
        A success message with paths to generated files, or an error description.
    """
    try:
        repo_root = os.path.abspath(__file__)
        while repo_root and not os.path.exists(os.path.join(repo_root, "pyproject.toml")):
            parent = os.path.dirname(repo_root)
            if parent == repo_root:
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                break
            repo_root = parent

        current_dir = os.path.dirname(os.path.abspath(__file__))
        scan_script = os.path.join(current_dir, "scan_and_generate.py")
        if not os.path.exists(scan_script):
            scan_script = os.path.join(repo_root, "tools", "scan_and_generate.py")

        results_dir = os.path.join(repo_root, "results")

        print(f"Starting GKE VPA Scraper: project={project_id or 'auto'}, clusters={cluster_filter or 'all'}, namespace={namespace_filter}, workload={workload_filter or 'all'}, include_system={include_system}...")

        cmd = ["python3", scan_script]
        if project_id:
            cmd.extend(["--project-id", project_id])
        if cluster_filter:
            cmd.extend(["--clusters", cluster_filter])
        if namespace_filter:
            cmd.extend(["--namespace", namespace_filter])
        if workload_filter:
            cmd.extend(["--workload", workload_filter])
        if include_system:
            cmd.extend(["--include-system"])

        res = subprocess.run(
            cmd,
            capture_output=True, text=True, check=True
        )

        return (
            f"SUCCESS: GKE VPA scan completed successfully.\n"
            f"Consolidated report generated at: {os.path.join(results_dir, 'vpa_recommendations_report.md')}\n"
            f"Output details:\n{res.stdout}"
        )
    except subprocess.CalledProcessError as e:
        return f"ERROR: Scraper script failed with exit code {e.returncode}.\nStderr:\n{e.stderr}\nStdout:\n{e.stdout}"
    except Exception as ex:
        return f"ERROR: Unexpected exception running GKE scan: {ex}"
