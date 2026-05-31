# Entry point to bootstrap and run system

# main.py
import asyncio
import logging
import os
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from src.coordinator import initialize_research_system_with_hooks
from src.telemetry import configure_token_telemetry

# Set up clean telemetry logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("research_system")


def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (existing vars win).

    Zero-dependency loader so TAVILY_API_KEY/ANTHROPIC_API_KEY reach the tools and
    SDK without requiring python-dotenv. Comments and blank lines are ignored.
    """
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


async def main():
    load_dotenv()

    dashboard_enabled = os.getenv("RESEARCH_ENABLE_LOCAL_DASHBOARD", "1").lower() not in {"0", "false", "no"}
    telemetry = configure_token_telemetry(start_dashboard=dashboard_enabled)
    if telemetry.dashboard_url:
        logger.info("Local token telemetry dashboard: %s", telemetry.dashboard_url)

    system = initialize_research_system_with_hooks()

    prompt = "Research the latest advancements in quantum-resistant encryption algorithms during 2026."

    logger.info("Starting Resilient Multi-Agent Deep Research System...")

    try:
        # Stream messages from the SDK and render them by type/content block.
        async for message in system.query_stream(prompt):
            if isinstance(message, SystemMessage):
                if message.subtype == "init":
                    print("🚀 [System] Session initialized.")

            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        # The Task tool is how the coordinator hands off to a subagent.
                        if block.name == "Task":
                            target = block.input.get("subagent_type", block.input.get("description", "subagent"))
                            print(f"\n🔄 [Handoff] Calling subagent: {target}")
                        else:
                            print(f"\n  🛠️ [Tool] {block.name} with args: {block.input}")

            elif isinstance(message, UserMessage):
                for block in message.content:
                    if isinstance(block, ToolResultBlock) and block.is_error:
                        print(f"\n  ⚠️ [Tool Error] {block.content}")

            elif isinstance(message, ResultMessage):
                print("\n\n✅ [Done]")
                if message.total_cost_usd is not None:
                    print(f"   Cost: ${message.total_cost_usd:.4f} | Turns: {message.num_turns}")

    except ConnectionError as ce:
        logger.critical(f"Network interface dropped during system execution: {str(ce)}")
        print("\n❌ System Error: Unable to communicate with Claude API. Please check your network connection.")

    except Exception as e:
        logger.critical(f"Uncaught critical infrastructure exception: {str(e)}")
        print(f"\n❌ Execution aborted. System safely spun down. Error logged.")

if __name__ == "__main__":
    asyncio.run(main())

