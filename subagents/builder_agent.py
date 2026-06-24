from google.adk.agents.llm_agent import Agent
from ..tools.builder_tool import compile_web_dashboard

web_builder = Agent(
    name="web_builder",
    model="gemini-2.5-flash",
    description="Compiles markdown GKE report findings into an interactive web dataset.",
    instruction="""
    You are the Web Dashboard Generator subagent. Your first and only action MUST be to immediately invoke the 'compile_web_dashboard' tool.
    Do NOT ask the user for confirmation or permission. Do NOT ask any questions.
    Just call the 'compile_web_dashboard' tool immediately to compile the database and copy assets.
    Once the tool completes, summarize the build status to the team.
    """,
    tools=[compile_web_dashboard],
)
