[developement.md](developement.md)

# Problem Statement:
Research work involves open-ended problems where it’s very difficult to predict the required steps in advance. You can’t hardcode a fixed path for exploring complex topics, as the process is inherently dynamic and path-dependent. When people conduct research, they tend to continuously update their approach based on discoveries, following leads that emerge during investigation.
## Scenario 3: Multi-Agent Research System
You are building a multi-agent research system using the Claude Agent SDK. A coordinator
agent delegates to specialized subagents: one searches the web, one analyzes documents, one
synthesizes findings, and one generates reports. The system researches topics and produces
comprehensive, cited reports.


Primary domains: Agentic Architecture & Orchestration, Tool Design & MCP Integration, Context
Management & Reliability


# How to implement
To build this multi-agent research system using the Claude Agent SDK, you must implement a Router/Orchestrator pattern


# Why Tavily?
what is TAVILYTavily is a specialized search engine built specifically for AI agents and Large Language Models (LLMs). 
Unlike traditional search engines designed for humans (like Google or Bing) that return a list of links, 
Tavily scans the live web, scrapes relevant pages, filters out junk text, 
and returns structured summaries optimized for AI consumption in a single API call

Key CapabilitiesAI-Optimized Search: Delivers concise summaries and clean context directly to LLMs instead of raw HTML or unparsed website links.Built for RAG: Tailored specifically for Retrieval-Augmented Generation (RAG) and AI agent workflows, significantly saving context window tokens.Multiple Endpoints: Includes specialized tools like Tavily Search (web searches), Tavily Extract (pulling raw content from specific pages), and Tavily Crawl (extracting raw documentation across entire site depths).Developer Ecosystem Integration: Native SDKs exist for Python and JavaScript, alongside seamless connectors for frameworks like LangChain, Vercel AI SDK, and Model Context Protocol (MCP) servers.How It Differs From Other Servicesvs. Google/Bing APIs: Standard search APIs provide links and generic meta descriptions. Tavily reads the source content, extracts the actual answer data, and structures it specifically for an LLM to read.vs. Perplexity API: While Perplexity gives you an end-user conversational AI response, Tavily gives developers highly customizable control over search depth, targeted domains, and raw data filtering so they can feed it into their own custom models.

## Payload Stress Test and Local Telemetry Dashboard

The coordinator now exposes a token-guard hook that compresses oversized synthesizer payloads and records token telemetry through OpenTelemetry.

### Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

### Generate a 100,000-word dummy payload and trigger the compression hook

```bash
python3 scripts/generate_dummy_research_data.py --words 100000 --hold-open
```

This command writes a large file to `generated/dummy_research_payload.txt`, invokes `compress_payload` through the coordinator hook, and starts a live dashboard at `http://127.0.0.1:8765` by default.

### Run the main coordinator with the dashboard enabled

```bash
RESEARCH_ENABLE_LOCAL_DASHBOARD=1 python3 main.py
```

### Optional pricing overrides for estimated token spend

```bash
export RESEARCH_INPUT_COST_PER_MILLION=3.0
export RESEARCH_OUTPUT_COST_PER_MILLION=15.0
```




