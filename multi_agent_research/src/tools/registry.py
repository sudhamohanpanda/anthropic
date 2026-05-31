"""In-process MCP server exposing the project's tools to the Claude Agent SDK.

The query()-based runner can only hand subagents tools that the SDK knows about.
We register the existing Tavily web search and local document reader as in-process
(SDK) MCP tools so the subagents call *our* implementations instead of the SDK's
built-in WebSearch/Read tools.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.tools.doc_reader import read_local_document
from src.tools.web_search import execute_web_search

# Claude Code namespaces in-process MCP tools as ``mcp__<server>__<tool>``.
MCP_SERVER_NAME = "research"
WEB_SEARCH_TOOL = f"mcp__{MCP_SERVER_NAME}__web_search"
READ_DOCUMENT_TOOL = f"mcp__{MCP_SERVER_NAME}__read_document"


def _text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def build_research_mcp_server(sdk_module: Any) -> Any:
    """Create the in-process ``research`` MCP server from the loaded SDK module.

    Takes the already-imported SDK module so the coordinator keeps its lazy-load
    (friendly-error-if-missing) behavior instead of importing the SDK at module top.
    """
    tool = sdk_module.tool

    @tool(
        "web_search",
        "Search the live web via Tavily and return source-attributed snippets. "
        "Pass a focused natural-language query.",
        {"query": str},
    )
    async def web_search(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        # execute_web_search is a blocking network call; keep the event loop free.
        text = await asyncio.to_thread(execute_web_search, query)
        return _text_result(text)

    @tool(
        "read_document",
        "Read a UTF-8 text document from the local workspace by file path.",
        {"file_path": str},
    )
    async def read_document(args: dict[str, Any]) -> dict[str, Any]:
        file_path = str(args.get("file_path", "")).strip()
        text = await asyncio.to_thread(read_local_document, file_path)
        return _text_result(text)

    return sdk_module.create_sdk_mcp_server(name=MCP_SERVER_NAME, tools=[web_search, read_document])