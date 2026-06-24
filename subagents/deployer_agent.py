from google.adk.agents.llm_agent import Agent
from ..tools.deployer_tool import deploy_dashboard_to_cloud_run

cloud_run_deployer = Agent(
    name="cloud_run_deployer",
    model="gemini-2.5-flash",
    description="Deploys containerized and source web applications to Google Cloud Run.",
    instruction="""
    You are the Cloud Run Deployer subagent. Your first and only action MUST be to immediately invoke the 'deploy_dashboard_to_cloud_run' tool.
    Do NOT ask the user for confirmation or permission. Do NOT ask any questions.
    Just call the 'deploy_dashboard_to_cloud_run' tool immediately to execute the deployment and return the public URL.
    Once the tool completes, summarize the deployment status and share the public endpoint URL.
    """,
    tools=[deploy_dashboard_to_cloud_run],
)
