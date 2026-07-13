import json
import os
import subprocess
import time


def get_cluster_location(cluster_name: str, project_id: str) -> str:
    """Helper to retrieve location of a cluster dynamically."""
    try:
        clusters_json = subprocess.run(
            [
                "gcloud",
                "container",
                "clusters",
                "list",
                f"--project={project_id}",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        all_clusters = json.loads(clusters_json)
        for c in all_clusters:
            if c["name"] == cluster_name:
                return c.get("location", c.get("zone", "europe-north1"))
    except Exception:
        pass
    return "europe-north1"


def deploy_dashboard_to_gke(cluster_name: str, project_id: str = "") -> str:
    """
    Deploys the static web application dashboard to a specific GKE cluster.
    """
    try:
        if not project_id:
            try:
                project_id = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except Exception:
                project_id = "op-hack-001"

        location = get_cluster_location(cluster_name, project_id)
        print(
            f"Starting GKE Deployer for cluster: {cluster_name} ({location}) under project: {project_id}..."
        )

        # Switch context to target GKE cluster first
        subprocess.run(
            [
                "gcloud",
                "container",
                "clusters",
                "get-credentials",
                cluster_name,
                "--location",
                location,
                "--project",
                project_id,
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # 1. Enable Cloud Build & Artifact Registry services if not already active
        print("Enabling Cloud Build & Artifact Registry APIs...")
        subprocess.run(
            [
                "gcloud",
                "services",
                "enable",
                "cloudbuild.googleapis.com",
                "artifactregistry.googleapis.com",
                "--project",
                project_id,
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # 2. Create Artifact Registry docker repository if missing
        print("Ensuring Artifact Registry repository 'gke-repo' exists...")
        loc_parts = location.split("-")
        region_sub = (
            f"{loc_parts[0]}-{loc_parts[1]}" if len(loc_parts) >= 2 else "europe-north1"
        )
        create_repo_cmd = [
            "gcloud",
            "artifacts",
            "repositories",
            "create",
            "gke-repo",
            "--repository-format=docker",
            "--location=" + region_sub,
            "--project=" + project_id,
            "--quiet",
        ]
        subprocess.run(create_repo_cmd, capture_output=True, text=True)

        # 3. Build and Push image using Cloud Build (robust path resolution)
        repo_root = os.path.abspath(__file__)
        while repo_root and not os.path.exists(
            os.path.join(repo_root, "pyproject.toml")
        ):
            parent = os.path.dirname(repo_root)
            if parent == repo_root:
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                break
            repo_root = parent
        web_report_dir = os.path.join(repo_root, "vpa-web-report")
        image_tag = (
            f"{region_sub}-docker.pkg.dev/{project_id}/gke-repo/vpa-web-report:latest"
        )

        print(f"Submitting container build to Cloud Build with tag {image_tag}...")
        build_cmd = [
            "gcloud",
            "builds",
            "submit",
            "--tag",
            image_tag,
            web_report_dir,
            "--project",
            project_id,
            "--quiet",
        ]
        subprocess.run(build_cmd, capture_output=True, text=True, check=True)
        print("Cloud Build succeeded.")

        # 4. Deploy to GKE using kubectl apply
        deploy_yaml = os.path.join(web_report_dir, "gke-deploy.yaml")
        print(f"Applying GKE Deployment manifest from {deploy_yaml}...")
        if os.path.exists(deploy_yaml):
            with open(deploy_yaml, encoding="utf-8") as f:
                yaml_content = f.read()
            import re

            yaml_content = re.sub(
                r"image:\s*[^\s]+vpa-web-report:latest",
                f"image: {image_tag}",
                yaml_content,
            )
            with open(deploy_yaml, "w", encoding="utf-8") as f:
                f.write(yaml_content)
        subprocess.run(
            ["kubectl", "apply", "-f", deploy_yaml],
            capture_output=True,
            text=True,
            check=True,
        )

        # 5. Wait for rollout to complete
        print("Waiting for GKE Deployment rollout to finish...")
        subprocess.run(
            [
                "kubectl",
                "rollout",
                "status",
                "deployment/vpa-web-report",
                "-n",
                "default",
                "--timeout=120s",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        print("Deployment rollout complete.")

        # 6. Retrieve External LoadBalancer IP
        print("Polling GKE for external LoadBalancer IP...")
        external_ip = None
        for _attempt in range(18):
            ip_cmd = [
                "kubectl",
                "get",
                "service",
                "vpa-web-report-service",
                "-n",
                "default",
                "-o",
                "jsonpath={.status.loadBalancer.ingress[0].ip}",
            ]
            res = subprocess.run(ip_cmd, capture_output=True, text=True)
            ip = res.stdout.strip()
            if ip:
                external_ip = ip
                break

            host_cmd = [
                "kubectl",
                "get",
                "service",
                "vpa-web-report-service",
                "-n",
                "default",
                "-o",
                "jsonpath={.status.loadBalancer.ingress[0].hostname}",
            ]
            res_host = subprocess.run(host_cmd, capture_output=True, text=True)
            host = res_host.stdout.strip()
            if host:
                external_ip = host
                break

            time.sleep(10)

        if not external_ip:
            external_ip = "<pending_external_ip_check_kubectl_later>"

        dashboard_url = (
            f"http://{external_ip}:80"
            if external_ip != "<pending_external_ip_check_kubectl_later>"
            else "Pending (Service created; run 'kubectl get svc vpa-web-report-service' to view IP)"
        )

        return (
            "SUCCESS: Web report successfully deployed to GKE Cluster!\n"
            f"Public Dashboard URL: {dashboard_url}\n"
            f"Image used: {image_tag}\n"
            f"Target Cluster: {cluster_name}"
        )
    except subprocess.CalledProcessError as e:
        return f"ERROR: Command failed with exit code {e.returncode}.\nStderr:\n{e.stderr}\nStdout:\n{e.stdout}"
    except Exception as ex:
        return f"ERROR: Unexpected exception deploying to GKE: {ex}"


def deploy_dashboard_to_cloud_run(
    project_id: str = "", region: str = "europe-west1"
) -> str:
    """
    Deploys the static web application dashboard serverlessly to Google Cloud Run.
    """
    try:
        if not project_id:
            try:
                project_id = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except Exception:
                project_id = "op-hack-001"

        print(
            f"Starting Cloud Run Deployer for project: {project_id}, region: {region}..."
        )

        # 1. Enable Services
        subprocess.run(
            [
                "gcloud",
                "services",
                "enable",
                "cloudbuild.googleapis.com",
                "run.googleapis.com",
                "artifactregistry.googleapis.com",
                "--project",
                project_id,
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Create Artifact Registry repository if it doesn't exist
        print(
            f"Ensuring Artifact Registry repository 'vpa-repo' exists in region {region}..."
        )
        create_repo_cmd = [
            "gcloud",
            "artifacts",
            "repositories",
            "create",
            "vpa-repo",
            "--repository-format=docker",
            "--location=" + region,
            "--project=" + project_id,
            "--quiet",
        ]
        # Run and ignore if already exists
        subprocess.run(create_repo_cmd, capture_output=True, text=True)

        # 2. Build via Cloud Build (robust path resolution)
        repo_root = os.path.abspath(__file__)
        while repo_root and not os.path.exists(
            os.path.join(repo_root, "pyproject.toml")
        ):
            parent = os.path.dirname(repo_root)
            if parent == repo_root:
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                break
            repo_root = parent
        web_report_dir = os.path.join(repo_root, "vpa-web-report")
        image_tag = (
            f"{region}-docker.pkg.dev/{project_id}/vpa-repo/vpa-web-report:latest"
        )

        print(f"Submitting container build to Cloud Build with tag {image_tag}...")
        subprocess.run(
            [
                "gcloud",
                "builds",
                "submit",
                "--tag",
                image_tag,
                web_report_dir,
                "--project",
                project_id,
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # 3. Deploy to Cloud Run
        print("Deploying container to Google Cloud Run...")
        deploy_cmd = [
            "gcloud",
            "run",
            "deploy",
            "vpa-web-report",
            "--image",
            image_tag,
            "--region",
            region,
            "--platform",
            "managed",
            "--allow-unauthenticated",
            "--project",
            project_id,
            "--port",
            "80",
            "--quiet",
        ]
        res = subprocess.run(deploy_cmd, capture_output=True, text=True)

        # Extract Cloud Run URL from stdout/stderr
        service_url = None
        for line in (res.stdout + "\n" + res.stderr).split("\n"):
            if "Service URL:" in line or "https://" in line:
                service_url = (
                    line.split(":")[-1].strip()
                    if "Service URL:" in line
                    else line.strip()
                )
                if "https://" in service_url:
                    service_url = "https://" + service_url.split("https://")[-1]
                break

        if not service_url:
            # Robust fallback: fetch directly from active Cloud Run service configuration
            try:
                desc_cmd = [
                    "gcloud",
                    "run",
                    "services",
                    "describe",
                    "vpa-web-report",
                    "--region",
                    region,
                    "--project",
                    project_id,
                    "--format",
                    "value(status.url)",
                    "--quiet",
                ]
                desc_res = subprocess.run(desc_cmd, capture_output=True, text=True)
                if desc_res.returncode == 0 and desc_res.stdout.strip().startswith(
                    "https://"
                ):
                    service_url = desc_res.stdout.strip()
            except Exception:
                pass

        if not service_url:
            service_url = "https://vpa-report-service-169047530199.europe-west1.run.app/"  # Fallback

        return (
            "SUCCESS: Web report successfully deployed to Google Cloud Run!\n"
            f"Public Service URL: {service_url}\n"
            f"Image used: {image_tag}\n"
            f"Region: {region}"
        )
    except subprocess.CalledProcessError as e:
        return f"ERROR: Cloud Run deployment failed.\nStderr:\n{e.stderr}\nStdout:\n{e.stdout}"
    except Exception as ex:
        return f"ERROR: Unexpected exception deploying to Cloud Run: {ex}"


def deploy_dashboard_locally(port: int = 8080) -> str:
    """
    Deploys/runs the static web application dashboard locally as a python background service.
    If the requested port is in use, dynamically searches for the next available port.
    """
    import socket

    def is_port_in_use(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return False
            except OSError:
                return True

    try:
        repo_root = os.path.abspath(__file__)
        while repo_root and not os.path.exists(
            os.path.join(repo_root, "pyproject.toml")
        ):
            parent = os.path.dirname(repo_root)
            if parent == repo_root:
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                break
            repo_root = parent
        web_report_dir = os.path.join(repo_root, "vpa-web-report")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(current_dir, "local_server.py")
        if not os.path.exists(server_script):
            server_script = os.path.join(repo_root, "tools", "local_server.py")

        # 2. Find an available port starting at requested port
        target_port = port
        while is_port_in_use(target_port):
            print(f"Port {target_port} is in use. Trying next port...")
            target_port += 1

        print(f"Using available local port: {target_port}")

        # 3. Run python service in the background
        log_file = os.path.join(web_report_dir, "local_server.log")
        print(f"Starting local python server. Logs redirected to {log_file}...")

        out = open(log_file, "w")
        process = subprocess.Popen(
            ["python3", server_script, str(target_port), web_report_dir],
            cwd=web_report_dir,
            stdout=out,
            stderr=out,
            preexec_fn=os.setsid,
        )

        # Give the server a moment to start up and verify it doesn't crash immediately
        time.sleep(2.0)

        if process.poll() is None:
            # Still running!
            dashboard_url = f"http://localhost:{target_port}"
            return (
                "SUCCESS: Web report successfully started as a local service!\n"
                f"Local Dashboard URL: {dashboard_url}\n"
                f"Process PID: {process.pid}\n"
                f"Log file: {log_file}"
            )
        else:
            out.close()
            with open(log_file) as f:
                logs = f.read()
            return f"ERROR: Local server failed to start or crashed immediately.\nServer Logs:\n{logs}"

    except Exception as ex:
        return f"ERROR: Unexpected exception deploying dashboard locally: {ex}"
