from google.adk.agents.llm_agent import Agent
from google.adk.tools import request_input
from ..tools.scraper_tool import run_project_vpa_scan

gke_scraper = Agent(
    name="gke_scraper",
    model="gemini-2.5-flash",
    description="Connects to GKE clusters and scans active VPA recommendation and metrics states.",
    instruction="""
    You are the GKE VPA Scraper subagent.
    
    CRITICAL: You MUST determine which Google Cloud project ID(s) to scan.
    - If a project ID is specified in the user's prompt or session context, extract it. If multiple project IDs are specified, extract all of them as a single, comma-separated string.
    - If NO project ID is specified in the prompt or context, you MUST immediately call the 'request_input' tool to ask the user to provide the project ID(s). Do NOT try to scan with default values or guess.
    
    Once you have the project ID(s), immediately call the 'run_project_vpa_scan' tool with the 'project_id' parameter.
    
    Do NOT ask any other questions or negotiate. Just use 'request_input' to get the project ID if missing, or run 'run_project_vpa_scan' immediately.
    Once the scan completes successfully, explain the results to the team.
    """,
    tools=[run_project_vpa_scan, request_input],
)

