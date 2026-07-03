---
name: "vpa-rightsizer"
description: "Scans GKE clusters for Vertical Pod Autoscaler (VPA) recommendations, generates clean optimized manifests, compiles a visual web dashboard, and deploys it to GKE."
---

# GKE Vertical Pod Autoscaler (VPA) Rightsizer Skill

This skill provides comprehensive capabilities to scan GKE clusters for right-sizing recommendations and build/deploy an interactive GKE VPA Autoscaler Hub dashboard.

## When to use
Use this skill when you or the user need to:
1. Scan one or multiple GKE clusters to find differences between active resource requests (CPU and memory) and GKE VPA recommended targets.
2. Generate clean, right-sized deployment manifests inside a local directory structure.
3. Build a premium, glassmorphic visual web dashboard dataset representing GKE resource metrics.
4. Deploy or redeploy the reporting dashboard server directly to GKE.

## Dynamic Ingestion & Execution
All underlying tools in this skill support **fully dynamic auto-discovery**:
- **Project Discovery**: If no Google Cloud Project ID is provided, the tool automatically executes `gcloud config get-value project` to scan the active project.
- **Cluster Discovery**: If no specific GKE clusters are specified, the tool queries all running clusters in the target project, switches credentials sequentially via `gcloud container clusters get-credentials`, and scrapes their VPA states.
- **Selective Scopes**: Supports optional filtering down to specific **Kubernetes namespaces** or **workload deployment names**.

## Key Available Tools
* `run_project_vpa_scan(project_id, cluster_filter, namespace_filter, workload_filter)`: Runs a complete multi-cluster VPA scan, switches cluster contexts, outputs optimized manifests, and writes a consolidated Markdown report.
* `compile_web_dashboard()`: Compiles the Markdown report into a structured JSON dataset and copies manifests for the Express web dashboard.
* `deploy_dashboard_to_gke(project_id, region)`: Automatically packages the web app folder, builds a container via Cloud Build, rolls it out to GKE, and returns the public LoadBalancer external IP.

## Example Invocation Flow
To invoke the entire pipeline via an agent turn, follow this sequence:
1. Query user or session context for target parameters.
2. Trigger the scan tool: `run_project_vpa_scan(project_id="", cluster_filter="", namespace_filter="default", workload_filter="")`.
3. Compile the build: `compile_web_dashboard()`.
4. Deploy/Restart GKE: `deploy_dashboard_to_gke()`.
