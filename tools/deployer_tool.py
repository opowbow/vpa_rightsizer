import os
import subprocess

def deploy_dashboard_to_cloud_run() -> str:
    """
    Enables necessary Google Cloud services and deploys the static web application 
    dashboard to Google Cloud Run from source, returning the final public service endpoint URL.
    
    Returns:
        The Cloud Run deploy results and public URL, or error details.
    """
    try:
        print("Starting Cloud Run Deployer subagent task...")
        
        # 1. Enable services (run, cloudbuild)
        subprocess.run(
            ["gcloud", "services", "enable", "run.googleapis.com", "cloudbuild.googleapis.com", "--project=gkeop002", "--quiet"],
            capture_output=True, text=True, check=True
        )
        
        # 2. Deploy service
        deploy_cmd = [
            "gcloud", "run", "deploy", "vpa-report-service",
            "--source", "/home/user/vpa-web-report",
            "--region", "europe-west1",
            "--allow-unauthenticated",
            "--project", "gkeop002",
            "--quiet"
        ]
        deploy_res = subprocess.run(deploy_cmd, capture_output=True, text=True, check=True)
        
        # 3. Retrieve URL
        url_cmd = [
            "gcloud", "run", "services", "describe", "vpa-report-service",
            "--platform", "managed", "--region", "europe-west1", "--project", "gkeop002",
            "--format", "value(status.url)"
        ]
        url_res = subprocess.run(url_cmd, capture_output=True, text=True, check=True)
        public_url = url_res.stdout.strip()
        
        return (
            "SUCCESS: Web report successfully deployed to Google Cloud Run!\n"
            f"Public Dashboard URL: {public_url}\n"
            f"Deploy output details:\n{deploy_res.stdout}"
        )
    except subprocess.CalledProcessError as e:
        return f"ERROR: gcloud command failed with exit code {e.returncode}.\nStderr:\n{e.stderr}\nStdout:\n{e.stdout}"
    except Exception as ex:
        return f"ERROR: Unexpected exception deploying to Cloud Run: {ex}"
