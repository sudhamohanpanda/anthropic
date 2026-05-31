# Subagent: Fact consolidation
# src/agents/synthesizer.py
synthesizer_agent_config = {
    "name": "synthesizer_agent",
    "description": "Merges multiple raw text documents into a unified, clean collection of notes.",
    "system_prompt": (
        "You are a Synthesizer Agent. Review information collected from both search and local documents. "
        "Your task is to merge duplicate items, resolve conflicting statements, "
        "and assemble notes organized by sub-topic. Retain every source link and file name reference."
    ),
    "tools": [] # Brain-only node; requires no external tool interactions
}
