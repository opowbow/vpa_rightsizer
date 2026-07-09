import os
import shutil
import subprocess
import json
import re

def compile_web_dashboard() -> str:
    """
    Natively parses the generated GKE scraper markdown report into a structured JSON dataset
    and copies the hierarchical deployment manifests into the web dashboard build directory.
    
    Returns:
        A success message, or error details.
    """
    try:
        # Resolve repo root path dynamically (robust to subfolders/agents)
        repo_root = os.path.abspath(__file__)
        while repo_root and not os.path.exists(os.path.join(repo_root, "pyproject.toml")):
            parent = os.path.dirname(repo_root)
            if parent == repo_root:
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                break
            repo_root = parent
        report_path = os.path.join(repo_root, "results", "vpa_recommendations_report.md")
        output_path = os.path.join(repo_root, "vpa-web-report", "public", "vpa-data.json")
        results_dir = os.path.join(repo_root, "results")
        web_report_dir = os.path.join(repo_root, "vpa-web-report")
        
        print("Starting native Python Web Dashboard Generator task...")
        
        # 1. Parse markdown report into JSON database natively
        if not os.path.exists(report_path):
            return f"ERROR: Markdown report not found at {report_path}"
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        lines = content.split("\n")
        workloads = []
        in_table = False
        
        for i in range(len(lines)):
            line = lines[i].strip()
            if line.startswith("|") and "Cluster" in line and "Namespace" in line:
                in_table = True
                continue
            
            if in_table:
                if not line.startswith("|"):
                    if line == "":
                        continue
                    else:
                        in_table = False
                        continue
                
                # Check for table header line (e.g. |---|---|...)
                if "---" in line:
                    continue
                    
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 11:
                    continue
                    
                def clean(val):
                    return val.replace("`", "").strip()
                    
                def parse_resources(res_str):
                    res = {"cpu": "N/A", "memory": "N/A"}
                    if not res_str or res_str == "N/A":
                        return res
                    clean_str = res_str.replace("<br>", " ").replace("`", "")
                    cpu_match = re.search(r"CPU:\s*([^\s]+)", clean_str, re.IGNORECASE)
                    mem_match = re.search(r"Mem:\s*([^\s]+)", clean_str, re.IGNORECASE)
                    if cpu_match:
                        res["cpu"] = cpu_match.group(1)
                    if mem_match:
                        res["memory"] = mem_match.group(1)
                    return res
                
                cluster = clean(parts[1])
                namespace = clean(parts[2])
                workload_name = clean(parts[3])
                vpa_status = parts[4]
                container_name = clean(parts[5])
                
                current = parse_resources(parts[6])
                recommended = parse_resources(parts[7])
                lower_bound = parse_resources(parts[8])
                upper_bound = parse_resources(parts[9])
                
                # Parse manifest link e.g. [adservice.yaml](file:///home/user/vpa-online-boutique/adservice.yaml)
                manifest_name = ""
                manifest_path = ""
                link_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", parts[10])
                if link_match:
                    manifest_name = link_match.group(1)
                    manifest_path = link_match.group(2)
                    if manifest_name.lower() in ("yaml", "link") and manifest_path:
                        manifest_name = os.path.basename(manifest_path.split("#")[0])
                else:
                    manifest_name = clean(parts[10])
                    manifest_path = parts[10]
                    
                workloads.append({
                    "cluster": cluster,
                    "namespace": namespace,
                    "workloadName": workload_name,
                    "vpaStatus": vpa_status,
                    "containerName": container_name,
                    "current": current,
                    "recommended": recommended,
                    "lowerBound": lower_bound,
                    "upperBound": upper_bound,
                    "manifestName": manifest_name,
                    "manifestPath": manifest_path
                })
                
        # Extract summary details using regex
        total_workloads = len(workloads)
        total_match = re.search(r"(?:Total Workloads Analyzed|Total Non-System Workloads Found)\*\*:\s*(\d+)", content, re.IGNORECASE)
        if total_match:
            total_workloads = int(total_match.group(1))
            
        vpa_enabled_count = len([w for w in workloads if w["vpaStatus"].startswith("Yes")])
        enabled_match = re.search(r"(?:VPA Enabled Workloads|Workloads with VPA Enabled)\*\*:\s*(\d+)", content, re.IGNORECASE)
        if enabled_match:
            vpa_enabled_count = int(enabled_match.group(1))
            
        cluster_vpa_status = {}
        support_match = re.search(r"VPA Support by Cluster\*\*:\s*([\s\S]*?)(?=\n\n|\n---)", content)
        if support_match:
            for l in support_match.group(1).split("\n"):
                m = re.search(r"`([^`]+)`:\s*\*\*(.*?)\*\*", l)
                if m:
                    cluster_vpa_status[m.group(1)] = m.group(2)
                    
        output_data = {
            "summary": {
                "totalWorkloads": total_workloads,
                "vpaEnabledCount": vpa_enabled_count,
                "clusterVpaStatus": cluster_vpa_status
            },
            "workloads": workloads
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
            
        # 2. Copy GKE manifests directories to the web build package dynamically
        copied_folders = []
        if os.path.exists(results_dir):
            for item in os.listdir(results_dir):
                if item.startswith("vpa-") and os.path.isdir(os.path.join(results_dir, item)):
                    src_dir = os.path.join(results_dir, item)
                    dest_dir = os.path.join(web_report_dir, item)
                    if os.path.exists(dest_dir):
                        shutil.rmtree(dest_dir)
                    os.makedirs(dest_dir, exist_ok=True)
                    for subitem in os.listdir(src_dir):
                        s = os.path.join(src_dir, subitem)
                        d = os.path.join(dest_dir, subitem)
                        if os.path.isdir(s):
                            shutil.copytree(s, d)
                        else:
                            shutil.copy2(s, d)
                    copied_folders.append(item)
                    
        return (
            "SUCCESS: Web report dataset generated natively in Python and hierarchical manifests copied successfully.\n"
            f"Successfully parsed and wrote {len(workloads)} workloads to {output_path}.\n"
            f"Copied manifest folders: {', '.join(copied_folders)}"
        )
    except Exception as ex:
        return f"ERROR: Unexpected exception compiling web dashboard natively: {ex}"


