# Subagent: Document parsing & reading

from src.tools.registry import READ_DOCUMENT_TOOL

analyzer_agent_config = {
    "name": "document_analyzer_agent",
    "description": "Optimized to parse, read, and pull information out of files in the workspace.",
    "system_prompt": (
        "You are a Document Analyzer Agent. Use Glob/Grep to locate relevant workspace "
        "documents, then read_document to read them. "
        "Extract definitions, exact quotes, tables, and statistics. "
        "Note down the file names as your source tracking reference."
    ),
    # read_document is our reader; Glob/Grep let the agent first locate candidate files.
    "tools": [READ_DOCUMENT_TOOL, "Glob", "Grep"],
}