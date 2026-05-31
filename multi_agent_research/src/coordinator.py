"""Supervisor agent definition, payload guards, and runtime hook helpers."""

from __future__ import annotations

import importlib
import inspect
import logging
import os
from collections.abc import Mapping, MutableMapping
from typing import Any

from src.agents.analyzer_agent import analyzer_agent_config
from src.agents.reporter import reporter_agent_config
from src.agents.search_agent import search_agent_config
from src.agents.synthesizer import synthesizer_agent_config
from src.telemetry import get_token_telemetry
from src.tools.registry import (
    MCP_SERVER_NAME,
    READ_DOCUMENT_TOOL,
    WEB_SEARCH_TOOL,
    build_research_mcp_server,
)

# Explicit tool allowlist for the query() path. With permission_mode="default" the
# SDK auto-allows exactly these (and denies others); under "bypassPermissions" the
# list is advisory. Includes the in-process MCP tools so tightening the mode still
# leaves the research tools usable. Subagent access is further scoped per-agent.
_COORDINATOR_ALLOWED_TOOLS = ["Task", "Agent", "Glob", "Grep", "Read", WEB_SEARCH_TOOL, READ_DOCUMENT_TOOL]

logger = logging.getLogger("research_system")

DEFAULT_MODEL = os.getenv("RESEARCH_MODEL", "claude-3-5-sonnet-latest")
# Unattended service default. Set RESEARCH_PERMISSION_MODE=default (plus the allowlist
# above) to require explicit allow decisions instead of bypassing permission checks.
DEFAULT_PERMISSION_MODE = os.getenv("RESEARCH_PERMISSION_MODE", "bypassPermissions")
SYNTHESIZER_AGENT_NAME = "synthesizer_agent"
TOKEN_MAX_THRESHOLD = 80_000
_SAFE_CHAR_BUDGET = TOKEN_MAX_THRESHOLD * 4
_SYSTEM_PROMPT = (
    "You are the Lead Research Coordinator. Your objective is to answer research questions "
    "by dynamically delegating work to your subagents.\n"
    "CRITICAL EXCEPTION INSTRUCTIONS:\n"
    "- If a subagent returns an 'Error' or 'Notice' status string, do not crash.\n"
    "- If web_search_agent fails, adapt by asking document_analyzer_agent to search local files instead.\n"
    "- If the tools fail repeatedly, generate the final report using your own knowledge, "
    "explicitly noting a connectivity warning in the introduction."
)
_AGENT_CONFIGS = [
    search_agent_config,
    analyzer_agent_config,
    synthesizer_agent_config,
    reporter_agent_config,
]


class SDKQueryRunner:
    """Small adapter that exposes an AgentRunner-like query_stream API over claude_agent_sdk.query."""

    def __init__(self, query_function: Any, options: Any):
        self._query_function = query_function
        self._options = options

    async def query_stream(self, prompt: str) -> Any:
        async for event in self._query_function(prompt=prompt, options=self._options):
            yield event


def estimate_token_count(text: str) -> int:
    """Approximate token count using a conservative 4-character heuristic."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def compress_payload(raw_text: str) -> str:
    """Reduce low-signal content before the synthesizer receives a large payload."""
    if not raw_text:
        return ""

    if estimate_token_count(raw_text) <= TOKEN_MAX_THRESHOLD:
        return raw_text.strip()

    logger.warning("Token threshold breached. Running payload compression safeguard.")
    compressed_lines: list[str] = []
    seen_recent_lines: set[str] = set()

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("---", "===", "DEBUG", "TRACE", "```")):
            continue
        if stripped in seen_recent_lines:
            continue
        compressed_lines.append(line)
        if len(seen_recent_lines) < 512:
            seen_recent_lines.add(stripped)

    combined = "\n".join(compressed_lines).strip() or raw_text.strip()
    if estimate_token_count(combined) <= TOKEN_MAX_THRESHOLD:
        return combined

    logger.error("Payload remains above the safe limit after filtering. Applying bounded trim.")
    head_budget = int(_SAFE_CHAR_BUDGET * 0.70)
    tail_budget = int(_SAFE_CHAR_BUDGET * 0.20)
    marker = "\n\n[... payload truncated by compress_payload ...]\n\n"
    bounded = f"{combined[:head_budget].rstrip()}{marker}{combined[-tail_budget:].lstrip()}"
    return bounded[:_SAFE_CHAR_BUDGET]


def _guard_synthesizer_payload(payload: str) -> tuple[str, int, int]:
    """Record telemetry and compress an oversized synthesizer payload.

    Single source of truth shared by the legacy event-shaped hook and the SDK
    PreToolUse guard, so both apply identical compression and telemetry regardless
    of which field the payload travels in (``raw_data`` vs ``prompt``). Returns
    ``(payload_to_use, token_estimate, saved_tokens)``; ``saved_tokens == 0`` means
    the payload was within budget and is returned unchanged.
    """
    incoming_tokens = estimate_token_count(payload)
    telemetry = get_token_telemetry()
    telemetry.record_input_tokens(
        incoming_tokens,
        attributes={"agent": SYNTHESIZER_AGENT_NAME, "phase": "synthesizer_handoff"},
    )
    logger.info("[Context Guard] Synthesizer incoming token volume: %s tokens.", incoming_tokens)

    if incoming_tokens <= TOKEN_MAX_THRESHOLD:
        return payload, incoming_tokens, 0

    optimized_payload = compress_payload(payload)
    optimized_tokens = estimate_token_count(optimized_payload)
    saved_tokens = max(0, incoming_tokens - optimized_tokens)

    telemetry.record_saved_tokens(
        saved_tokens,
        attributes={"agent": SYNTHESIZER_AGENT_NAME, "phase": "compression"},
    )
    telemetry.record_estimated_cost(
        input_tokens=optimized_tokens,
        output_tokens=0,
        model=DEFAULT_MODEL,
        attributes={"agent": SYNTHESIZER_AGENT_NAME, "phase": "compression"},
    )
    logger.info(
        "[Context Guard] Compression complete. New volume: %s tokens (saved %s).",
        optimized_tokens,
        saved_tokens,
    )
    return optimized_payload, optimized_tokens, saved_tokens


def _event_get(event: Any, key: str, default: Any = None) -> Any:
    if isinstance(event, Mapping):
        return event.get(key, default)
    return getattr(event, key, default)


def _event_arguments(event: Any) -> MutableMapping[str, Any]:
    if isinstance(event, MutableMapping):
        arguments = event.get("arguments")
        if isinstance(arguments, MutableMapping):
            return arguments
        arguments = {}
        event["arguments"] = arguments
        return arguments

    arguments = getattr(event, "arguments", None)
    if isinstance(arguments, MutableMapping):
        return arguments

    fallback: MutableMapping[str, Any] = {}
    try:
        setattr(event, "arguments", fallback)
    except (AttributeError, TypeError):
        pass
    return fallback


async def handle_tool_error(event: Any, context: MutableMapping[str, Any]) -> None:
    """Intercept tool failures before they bubble up to crash a sub-agent."""
    tool_name = _event_get(event, "tool_name", "unknown_tool")
    agent_name = _event_get(event, "agent_name", "unknown_agent")
    error_message = _event_get(event, "error_message", "No error details were provided.")

    logger.error("[Hook - Tool Error] Tool '%s' failed in agent '%s'.", tool_name, agent_name)
    logger.error("Error Details: %s", error_message)
    context["retry_hint"] = "The last tool call failed. Try a different query or simplify parameters."


async def handle_subagent_error(event: Any, context: MutableMapping[str, Any]) -> None:
    """Intercept sub-agent execution crashes and provide a deterministic fallback."""
    agent_name = _event_get(event, "agent_name", "unknown_agent")
    logger.error("[Hook - Agent Crash] Subagent '%s' failed during processing.", agent_name)

    if agent_name == "web_search_agent":
        context["prefer_local_documents"] = True
        logger.info("Redirecting coordinator priority to the local document parsing pipeline.")


async def check_synthesizer_tokens_hook(event: Any, context: MutableMapping[str, Any]) -> Any:
    """Inspect synthesizer handoffs and compress oversized payloads in place."""
    target_agent = _event_get(event, "target_agent")
    if target_agent != SYNTHESIZER_AGENT_NAME:
        return event

    arguments = _event_arguments(event)
    raw_payload = str(arguments.get("raw_data", ""))

    optimized_payload, token_estimate, saved_tokens = _guard_synthesizer_payload(raw_payload)

    arguments["raw_data"] = optimized_payload
    context["token_guard_triggered"] = saved_tokens > 0
    context["token_estimate"] = token_estimate
    if saved_tokens > 0:
        context["saved_tokens"] = saved_tokens
    return event


# ---------------------------------------------------------------------------
# SDK-native hook callbacks (query()-path).
#
# The handlers above target the (currently unavailable) AgentRunner event model.
# The SDK's query() path delivers hooks with the signature
#   async def cb(input_data: dict, tool_use_id: str | None, context) -> dict
# and a different payload shape, so the query path uses the adapters below.
# ---------------------------------------------------------------------------

_DELEGATION_TOOL_NAMES = {"Task", "Agent"}


async def pre_tool_use_token_guard(input_data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
    """PreToolUse hook: compress oversized payloads handed to the synthesizer subagent.

    Coordinator-to-subagent delegation arrives as a Task/Agent tool call whose
    ``tool_input`` carries ``subagent_type`` and ``prompt``. When the synthesizer
    is the target and the prompt exceeds the safe token budget, rewrite the prompt
    in place via ``updatedInput`` and record telemetry.
    """
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {}) or {}
    if tool_name not in _DELEGATION_TOOL_NAMES:
        return {}
    if tool_input.get("subagent_type") != SYNTHESIZER_AGENT_NAME:
        return {}

    payload = str(tool_input.get("prompt", ""))
    optimized_payload, _token_estimate, saved_tokens = _guard_synthesizer_payload(payload)
    if saved_tokens <= 0:
        return {}

    updated_input = dict(tool_input)
    updated_input["prompt"] = optimized_payload
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated_input,
        }
    }


async def post_tool_failure_logger(input_data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
    """PostToolUseFailure hook: log tool failures and feed a recovery hint back to the model."""
    tool_name = input_data.get("tool_name", "unknown_tool")
    agent_type = input_data.get("agent_type", "coordinator")
    error_message = input_data.get("error", "No error details were provided.")
    logger.error("[Hook - Tool Failure] Tool '%s' failed in '%s': %s", tool_name, agent_type, error_message)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUseFailure",
            "additionalContext": (
                "The last tool call failed. Try a different query or simplify parameters; "
                "if web search keeps failing, fall back to local documents or internal knowledge."
            ),
        }
    }


async def subagent_stop_logger(input_data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
    """SubagentStop hook: record when a subagent finishes for observability."""
    agent_type = input_data.get("agent_type", "unknown_agent")
    logger.info("[Hook - Subagent Stop] Subagent '%s' finished.", agent_type)
    return {}


def _load_sdk_module() -> Any:
    try:
        return importlib.import_module("claude_agent_sdk")
    except ImportError as exc:
        raise RuntimeError(
            "The Claude Agent SDK is not installed. Install project dependencies before running the coordinator."
        ) from exc


def _load_agent_runner_class(sdk_module: Any) -> type[Any] | None:
    return getattr(sdk_module, "AgentRunner", None)


def _build_sdk_agents(sdk_module: Any) -> dict[str, Any] | None:
    agent_definition_class = getattr(sdk_module, "AgentDefinition", None)
    if agent_definition_class is None:
        return None

    sdk_agents: dict[str, Any] = {}
    for config in _AGENT_CONFIGS:
        tool_names = [tool for tool in config.get("tools", []) if isinstance(tool, str)]
        # Grant the subagent access to any in-process MCP server its tools reference.
        mcp_server_names = sorted(
            {tool.split("__")[1] for tool in tool_names if tool.startswith("mcp__")}
        )
        sdk_agents[config["name"]] = agent_definition_class(
            description=config["description"],
            prompt=config["system_prompt"],
            tools=tool_names,
            mcpServers=mcp_server_names or None,
        )
    return sdk_agents


def _build_query_hooks(sdk_module: Any, enable_generation_guard: bool) -> dict[str, list[Any]] | None:
    """Map the coordinator's reliability hooks onto the SDK's query()-path hook events."""
    hook_matcher_class = getattr(sdk_module, "HookMatcher", None)
    if hook_matcher_class is None:
        logger.info("HookMatcher is unavailable in the installed SDK; running query() path without hooks.")
        return None

    hooks: dict[str, list[Any]] = {
        "PostToolUseFailure": [hook_matcher_class(hooks=[post_tool_failure_logger])],
        "SubagentStop": [hook_matcher_class(hooks=[subagent_stop_logger])],
    }
    if enable_generation_guard:
        hooks["PreToolUse"] = [hook_matcher_class(hooks=[pre_tool_use_token_guard])]
    return hooks


def _create_query_runner(sdk_module: Any, enable_generation_guard: bool = True) -> SDKQueryRunner:
    query_function = getattr(sdk_module, "query", None)
    options_class = getattr(sdk_module, "ClaudeAgentOptions", None)
    if query_function is None or options_class is None:
        raise RuntimeError("The installed Claude Agent SDK does not expose query() and ClaudeAgentOptions.")

    research_server = build_research_mcp_server(sdk_module)

    options = options_class(
        model=DEFAULT_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        max_turns=12,
        include_partial_messages=True,
        agents=_build_sdk_agents(sdk_module),
        mcp_servers={MCP_SERVER_NAME: research_server},
        allowed_tools=_COORDINATOR_ALLOWED_TOOLS,
        # Defaults to "bypassPermissions" for unattended operation; override with
        # RESEARCH_PERMISSION_MODE. Subagent tool access is also scoped per-agent.
        permission_mode=DEFAULT_PERMISSION_MODE,
        hooks=_build_query_hooks(sdk_module, enable_generation_guard),
        cwd=os.getcwd(),
    )
    return SDKQueryRunner(query_function=query_function, options=options)


def _filter_supported_runner_kwargs(runner_class: type[Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(runner_class)
    parameters = signature.parameters
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return kwargs
    return {key: value for key, value in kwargs.items() if key in parameters}


def _build_runner_kwargs(enable_generation_guard: bool) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "system_prompt": _SYSTEM_PROMPT,
        "agents": _AGENT_CONFIGS,
        "on_tool_error": handle_tool_error,
        "on_agent_error": handle_subagent_error,
    }

    if enable_generation_guard:
        kwargs["on_generation_start"] = check_synthesizer_tokens_hook

    return kwargs


def _create_agent_runner(enable_generation_guard: bool = True) -> Any:
    sdk_module = _load_sdk_module()
    runner_class = _load_agent_runner_class(sdk_module)
    if runner_class is None:
        logger.info("AgentRunner is unavailable in the installed Claude Agent SDK. Falling back to query()-based runner.")
        return _create_query_runner(sdk_module, enable_generation_guard=enable_generation_guard)

    runner_kwargs = _filter_supported_runner_kwargs(
        runner_class,
        _build_runner_kwargs(enable_generation_guard=enable_generation_guard),
    )
    return runner_class(**runner_kwargs)


def initialize_research_system_with_guards() -> Any:
    """Configure the research supervisor with token-guard hooks enabled."""
    return _create_agent_runner(enable_generation_guard=True)


def initialize_research_system_with_hooks() -> Any:
    """Configure the main supervisor node with error handling and token guards."""
    return _create_agent_runner(enable_generation_guard=True)

