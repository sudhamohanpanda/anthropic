"""Generate a large dummy research payload and trigger the coordinator compression hook."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.coordinator import (  # noqa: E402
    SYNTHESIZER_AGENT_NAME,
    check_synthesizer_tokens_hook,
    estimate_token_count,
)
from src.telemetry import configure_token_telemetry  # noqa: E402

LEXICON = {
    "subjects": [
        "quantum-safe encryption",
        "autonomous research systems",
        "distributed observability",
        "retrieval orchestration",
        "context compression",
    ],
    "methods": [
        "benchmark triangulation",
        "comparative evaluation",
        "ablation analysis",
        "cross-source validation",
        "controlled load testing",
    ],
    "findings": [
        "improved recall under noisy inputs",
        "lower coordination latency",
        "higher citation consistency",
        "better fallback behavior",
        "reduced token waste during synthesis",
    ],
    "qualifiers": [
        "significantly",
        "consistently",
        "measurably",
        "operationally",
        "empirically",
    ],
}


def build_word_list(target_words: int) -> list[str]:
    words: list[str] = []
    section_index = 0

    while len(words) < target_words:
        subject = LEXICON["subjects"][section_index % len(LEXICON["subjects"])]
        method = LEXICON["methods"][(section_index + 1) % len(LEXICON["methods"])]
        finding = LEXICON["findings"][(section_index + 2) % len(LEXICON["findings"])]
        qualifier = LEXICON["qualifiers"][(section_index + 3) % len(LEXICON["qualifiers"])]

        paragraph = (
            f"Section {section_index + 1} investigates {subject} using {method}. "
            f"The simulated researchers {qualifier} reported {finding}. "
            "Each observation includes provenance markers, synthetic citations, and repeated long-form notes "
            "so that downstream compression routines must collapse redundant material before synthesis."
        )
        words.extend(paragraph.split())
        section_index += 1

    return words[:target_words]


async def trigger_hook(payload: str) -> tuple[dict[str, object], dict[str, object]]:
    event = {
        "target_agent": SYNTHESIZER_AGENT_NAME,
        "arguments": {
            "raw_data": payload,
        },
    }
    context: dict[str, object] = {}
    await check_synthesizer_tokens_hook(event, context)
    return event, context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=int, default=100_000, help="Target number of words to generate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "generated" / "dummy_research_payload.txt",
        help="Where to write the generated text file.",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8765,
        help="Port for the local telemetry dashboard.",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip starting the local telemetry dashboard.",
    )
    parser.add_argument(
        "--hold-open",
        action="store_true",
        help="Keep the process alive after generation so the dashboard stays available.",
    )
    args = parser.parse_args()

    telemetry = configure_token_telemetry(
        dashboard_port=args.dashboard_port,
        enable_console_exporter=False,
        start_dashboard=not args.no_dashboard,
    )

    words = build_word_list(args.words)
    payload = " ".join(words)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")

    original_tokens = estimate_token_count(payload)
    event, context = asyncio.run(trigger_hook(payload))
    optimized_payload = str(event["arguments"]["raw_data"])
    optimized_tokens = estimate_token_count(optimized_payload)
    saved_tokens = original_tokens - optimized_tokens
    telemetry.force_flush()

    print(f"Generated payload file: {args.output}")
    print(f"Word count: {len(words):,}")
    print(f"Original token estimate: {original_tokens:,}")
    print(f"Optimized token estimate: {optimized_tokens:,}")
    print(f"Saved tokens: {saved_tokens:,}")
    print(f"Compression hook triggered: {context.get('token_guard_triggered', False)}")
    if telemetry.dashboard_url:
        print(f"Dashboard: {telemetry.dashboard_url}")

    if args.hold_open and telemetry.dashboard_url:
        print("Dashboard server is running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    telemetry.shutdown()


if __name__ == "__main__":
    main()

