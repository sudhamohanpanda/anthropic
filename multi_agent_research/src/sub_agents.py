from claude_agent_sdk import Agent, Coordinator, Tool

# Step 1: Define subagent capabilities as tools for the Coordinator
def invoke_web_search(query: str) -> dict:
    """Delegates a search task to the Web Search Agent."""
    return web_search_agent.run(query)

def invoke_doc_analyzer(file_id: str, criteria: str) -> dict:
    """Delegates file parsing to the Document Analyzer Agent."""
    return doc_analyzer_agent.run(file_id, criteria)

def invoke_synthesizer(raw_data: list) -> dict:
    """Delegates data merging and cross-referencing to the Synthesizer Agent."""
    return synthesizer_agent.run(raw_data)

def invoke_report_generator(synthesized_data: dict) -> str:
    """Delegates final document writing to the Report Generator Agent."""
    return report_generator_agent.run(synthesized_data)

# Step 2: Initialize the Coordinator with delegation tools
coordinator = Agent(
    model="claude-3-5-sonnet-latest",
    system="You are the Coordinator. Break down research queries. Run search and analyzer tasks, pass results to the synthesizer, and send the final synthesis to the report generator.",
    tools=[
        Tool(invoke_web_search),
        Tool(invoke_doc_analyzer),
        Tool(invoke_synthesizer),
        Tool(invoke_report_generator)
    ]
)
