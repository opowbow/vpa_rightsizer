from typing import AsyncGenerator
import os
from google.genai.types import Content, Part
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from .subagents.scraper_agent import gke_scraper
from .subagents.builder_agent import web_builder
from .subagents.deployer_agent import cloud_run_deployer

class RootVpaPipeline(BaseAgent):
    """
    A robust custom orchestrator pipeline for GKE VPA Right-sizing.
    Enforces sequential execution, checks prerequisites, and halts early with clear logs upon failure.
    """
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Helper to emit text events
        def info_event(text: str) -> Event:
            return Event(author=self.name, content=Content(parts=[Part(text=text)]))
            
        report_path = "/home/user/agent-projects/vpa_rightsizer/results/vpa_recommendations_report.md"
        web_json_path = "/home/user/vpa-web-report/public/vpa-data.json"
        
        yield info_event("🔄 [Pipeline] Initializing GKE VPA Right-sizing Pipeline...")
        
        # 1. Run Scraper Subagent
        yield info_event("🚀 [Pipeline] Step 1: Executing GKE VPA Scraper subagent...")
        if len(self.sub_agents) < 3:
            yield info_event("❌ [Pipeline] Error: Expected at least 3 subagents (scraper, builder, deployer).")
            return
            
        scraper_agent = self.sub_agents[0]
        async for event in scraper_agent.run_async(ctx):
            yield event
            
        # Post-Scraper Verification
        yield info_event("🔍 [Pipeline] Verifying scraper output...")
        if not os.path.exists(report_path):
            yield info_event(f"❌ [Pipeline] Error: Scraper failed to generate report at {report_path}. Halting pipeline.")
            return
        yield info_event(f"✅ [Pipeline] Scraper output verified: {report_path} exists.")
        
        # 2. Run Builder Subagent
        yield info_event("🚀 [Pipeline] Step 2: Executing Web Dashboard Builder subagent...")
        builder_agent = self.sub_agents[1]
        async for event in builder_agent.run_async(ctx):
            yield event
            
        # Post-Builder Verification
        yield info_event("🔍 [Pipeline] Verifying web builder output...")
        if not os.path.exists(web_json_path):
            yield info_event(f"❌ [Pipeline] Error: Web Builder failed to compile dataset at {web_json_path}. Halting pipeline.")
            return
        yield info_event(f"✅ [Pipeline] Web Builder output verified: {web_json_path} exists.")
        
        # 3. Run Deployer Subagent
        yield info_event("🚀 [Pipeline] Step 3: Executing Cloud Run Deployer subagent...")
        deployer_agent = self.sub_agents[2]
        async for event in deployer_agent.run_async(ctx):
            yield event
            
        yield info_event("🏁 [Pipeline] GKE VPA Right-sizing Pipeline completed successfully!")

# Root GKE VPA Rightsizer Custom Multi-Agent Team Orchestrator
root_agent = RootVpaPipeline(
    name="vpa_rightsizer",
    sub_agents=[
        gke_scraper,
        web_builder,
        cloud_run_deployer
    ],
    description="End-to-end GKE VPA Scraper, Web Dashboard Generator, and Cloud Run Deployer custom pipeline."
)

