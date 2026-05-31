# Subagent: Web queries & retrieval

from src.tools.registry import WEB_SEARCH_TOOL

search_agent_config = {
    "name": "web_search_agent",
    "description": "Expert at execution of targeted web searches to acquire live data and source references.",
    "system_prompt": (
        "You are a meticulous Web Search Agent. Your goal is to gather highly accurate data. "
        "Use the web_search tool to retrieve live results. "
        "Always extract raw content and associate it explicitly with the exact Source URL. "
        "Do not summarize or lose data; return dense, fact-filled findings."
    ),
    # Restricted to our Tavily-backed tool so the subagent cannot fall back to the
    # SDK's built-in WebSearch.
    "tools": [WEB_SEARCH_TOOL],
}