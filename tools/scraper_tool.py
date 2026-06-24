import os
import subprocess
import shutil
import re
from datetime import datetime, timezone

def run_project_vpa_scan(project_id: str = "gkeop002", cluster_filter: str = "") -> str:
    """
    Executes a project-wide GKE cluster resource scan across GKE clusters
    (fetching active Kubernetes VPA recommendations and Cloud Monitoring fallback metrics)
    for one or more project IDs (comma-separated).
    Generates updated resource manifests and consolidates all findings into a single markdown recommendations report.
    
    Args:
        project_id: The Google Cloud project ID(s) to scan. Can be a single project ID or a comma-separated list of IDs.
        cluster_filter: Optional comma-separated list of specific cluster names to scan (e.g. 'online-boutique,my-gke-cluster').
        
    Returns:
        A success message with paths to generated files, or an error description.
    """
    try:
        # Parse project IDs
        projects = [p.strip() for p in project_id.split(",") if p.strip()]
        if not projects:
            return "ERROR: No valid project IDs provided."
            
        print(f"Starting GKE VPA Scraper subagent task for projects={projects}, clusters={cluster_filter or 'ALL'}...")
        
        project_reports = []
        stdouts = []
        
        for proj in projects:
            print(f"-> Running GKE scan for project: {proj}...")
            cmd = ["python3", "/home/user/scan_and_generate.py", "--project-id", proj]
            if cluster_filter:
                cmd.extend(["--clusters", cluster_filter])
                
            res = subprocess.run(
                cmd,
                capture_output=True, text=True, check=True
            )
            stdouts.append(f"--- Project {proj} Output ---\n{res.stdout}")
            
            # Copy/rename the generated report to a project-specific report
            src_report = "/home/user/agent-projects/vpa_rightsizer/results/vpa_recommendations_report.md"
            project_report = f"/home/user/agent-projects/vpa_rightsizer/results/vpa_recommendations_report_{proj}.md"
            if os.path.exists(src_report):
                shutil.copy2(src_report, project_report)
                project_reports.append((proj, project_report))
                
        # Consolidate reports if we have multiple projects
        if len(projects) > 1:
            print("Consolidating reports from multiple projects...")
            total_clusters = 0
            total_workloads = 0
            vpa_enabled_count = 0
            monitoring_fallback_count = 0
            all_table_rows = []
            cluster_findings = []
            
            for proj, report_path in project_reports:
                with open(report_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Parse summary metrics using Regex
                clusters_match = re.search(r"Total Clusters Scanned\*\*:\s*(\d+)", content)
                workloads_match = re.search(r"Total Non-System Workloads Found\*\*:\s*(\d+)", content)
                vpa_enabled_match = re.search(r"Workloads with VPA Enabled\*\*:\s*(\d+)", content)
                monitoring_match = re.search(r"Cloud Monitoring Fallbacks\*\*:\s*(\d+)", content)
                
                if clusters_match:
                    total_clusters += int(clusters_match.group(1))
                if workloads_match:
                    total_workloads += int(workloads_match.group(1))
                if vpa_enabled_match:
                    vpa_enabled_count += int(vpa_enabled_match.group(1))
                if monitoring_match:
                    monitoring_fallback_count += int(monitoring_match.group(1))
                    
                # Parse cluster findings list
                findings_match = re.search(r"### 🔍 Cluster-Specific Findings\s*\n([\s\S]*?)(?=\n\n|\n##)", content)
                if findings_match:
                    cluster_findings.append(f"#### Project `{proj}` Findings:\n" + findings_match.group(1).strip())
                    
                # Extract detailed table rows
                lines = content.split("\n")
                in_table = False
                for line in lines:
                    line = line.strip()
                    if line.startswith("|") and "Cluster Name" in line:
                        in_table = True
                        continue
                    if in_table:
                        if not line.startswith("|"):
                            in_table = False
                            continue
                        if "---" in line:
                            continue
                        # If it is a normal row
                        all_table_rows.append(line)
            
            # Construct consolidated report
            vpa_percentage = (vpa_enabled_count / total_workloads * 100) if total_workloads > 0 else 0.0
            
            md_content = []
            md_content.append("# 📊 GKE Workloads & Vertical Pod Autoscaler (VPA) Recommendations Report (Consolidated)\n")
            md_content.append(f"**Generated On**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            md_content.append("## 📈 Executive Summary\n")
            md_content.append(f"- **Total Projects Scanned**: {len(projects)} (`{', '.join(projects)}`)\n")
            md_content.append(f"- **Total Clusters Scanned**: {total_clusters}\n")
            md_content.append(f"- **Total Non-System Workloads Found**: {total_workloads}\n")
            md_content.append(f"- **Workloads with VPA Enabled**: {vpa_enabled_count} ({vpa_percentage:.1f}%)\n")
            md_content.append(f"- **Cloud Monitoring Fallbacks**: {monitoring_fallback_count}\n")
            
            md_content.append("\n### 🔍 Cluster-Specific Findings\n")
            md_content.append("\n\n".join(cluster_findings))
            
            md_content.append("\n\n## 📋 Detailed Workload Recommendation Table\n")
            md_content.append("| Cluster Name | Namespace | Workload Name | VPA Status & Mode | Container Name | Current Requests | Recommended Targets | Lower Bounds | Upper Bounds | Manifest Path |\n")
            md_content.append("|---|---|---|---|---|---|---|---|---|---|\n")
            md_content.append("\n".join(all_table_rows) + "\n")
            
            md_content.append("\n\n> [!NOTE]\n")
            md_content.append("> Clean deployment manifests are written to `/home/user/agent-projects/vpa_rightsizer/results/vpa-<project_id>/vpa-<cluster_name>/<namespace_name>/` directories on the local file system. If recommended values were found (via VPA or Cloud Monitoring fallback), they have been applied directly to the container `resources.requests` specifications.\n")
            
            combined_report_path = "/home/user/agent-projects/vpa_rightsizer/results/vpa_recommendations_report.md"
            with open(combined_report_path, "w", encoding="utf-8") as f:
                f.write("".join(md_content))
                
        return (
            f"SUCCESS: GKE VPA scan completed successfully for projects: {', '.join(projects)}.\n"
            "Consolidated report generated at: /home/user/agent-projects/vpa_rightsizer/results/vpa_recommendations_report.md\n"
            f"Output details:\n" + "\n".join(stdouts)
        )
    except subprocess.CalledProcessError as e:
        return f"ERROR: Scraper script failed with exit code {e.returncode}.\nStderr:\n{e.stderr}\nStdout:\n{e.stdout}"
    except Exception as ex:
        return f"ERROR: Unexpected exception running GKE scan: {ex}"

