# Subagent: Markdown formatting
# src/agents/reporter.py
from pydantic import BaseModel

class ReportOutputSchema(BaseModel):
    title: str
    executive_summary: str
    body_markdown: str
    citations_list: list[str]

reporter_agent_config = {
    "name": "report_generator_agent",
    "description": "Converts organized, raw notes into beautiful, professional, cited Markdown documents.",
    "system_prompt": (
        "You are a Report Generator Agent. Take synthesized notes and arrange them "
        "into a detailed research report. Use inline bracket citations like [1], [2] matching "
        "the bibliography links at the bottom. Return your response matching the structured output criteria."
    ),
    "tools": [],
    "output_schema": ReportOutputSchema # Assures structured, parseable production results
}
