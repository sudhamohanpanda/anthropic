"""Search engine API interface (for example Tavily or Exa)."""

from __future__ import annotations

import importlib
import logging
import os
from typing import Any

logger = logging.getLogger("research_system")


def _load_tavily_client() -> type[Any] | None:
    try:
        tavily_module = importlib.import_module("tavily")
    except ImportError:
        return None
    return getattr(tavily_module, "TavilyClient", None)


def execute_web_search(query: str, max_retries: int = 2) -> str:
    """Query the internet with built-in exception handling and fallback strategies."""
    if not query.strip():
        return "Notice: Search skipped because the query was empty."

    tavily_client_class = _load_tavily_client()
    if tavily_client_class is None:
        logger.error("tavily-python is not installed.")
        return "Error: Web search dependency 'tavily-python' is not installed. Proceeding using internal knowledge only."

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.error("TAVILY_API_KEY environment variable is missing.")
        return "Error: Web search tool is unconfigured. Proceeding using internal knowledge only."

    tavily = tavily_client_class(api_key=api_key)

    for attempt in range(max_retries + 1):
        try:
            response = tavily.search(query=query, max_results=5, timeout=10)
            results: list[str] = []
            for result in response.get("results", []):
                source_url = result.get("url", "unknown")
                content = result.get("content", "")
                results.append(f"Source: {source_url}\nContent: {content}\n---")

            if not results:
                return f"Notice: Search completed successfully for '{query}', but yielded zero relevant results."

            return "\n".join(results)

        except Exception as exc:  # pragma: no cover - depends on external service availability.
            logger.warning("Search attempt %s failed for query '%s': %s", attempt + 1, query, exc)
            if attempt >= max_retries:
                return f"Error: Web search failed due to a network or upstream server error: {exc}"

    return f"Error: Web search ended unexpectedly for query '{query}'."


def execute_web_search_with_retry(query: str, max_retries: int = 2) -> str:
    """Backward-compatible alias for older code paths."""
    return execute_web_search(query=query, max_retries=max_retries)

