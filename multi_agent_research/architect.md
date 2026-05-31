# Architect

## Agent Architecture and Role Definitions

1. **Coordinator Agent**
   - The central controller of the system.
   - Breaks down the research prompt into an execution plan.
   - Invokes sub-agents sequentially or in parallel via tools.
   - Tracks state and handles execution lifecycle hooks.

2. **Web Search Agent**
   - Specialized in query optimization.
   - Interfaces with external search APIs.
   - Filters results and extracts relevant raw snippets with accurate source URLs.

3. **Document Analyzer Agent**
   - Optimized for long-context windows.
   - Processes uploaded files and extracts structured sections.
   - Matches findings against user criteria.

4. **Synthesizer Agent**
   - Aggregates data from search results and document analysis.
   - Resolves conflicting information and de-duplicates facts.
   - Structures notes into a cross-referenced knowledge base.

5. **Report Generator Agent**
   - Focuses on output formatting.
   - Transforms synthesized data into a publication-ready Markdown report.
   - Includes inline citations and a bibliography.

## Advantages of Coordinator Agent
- **Centralized Control**: The coordinator agent orchestrates the entire workflow, ensuring that each sub-agent 
executes in the correct sequence and that their outputs are properly integrated.

### State Management & Multi-Turn Handoffs

To ensure reliable multi-turn handoffs without losing critical context, apply these production practices:

- **Pass-Through Context Tunnels**: Sub-agents must return data in a strict JSON schema containing both the core fact and provenance metadata (for example, `source_url`, `document_page`, `confidence_score`).
- **Token Optimization**: Do not return raw HTML or full documents to the Coordinator. Web Search and Document Analyzer agents should compress outputs into dense semantic chunks before handoff.
- **Lifecycle Hooks for Error Correction**: Implement `on_tool_error` or validation hooks. If the Synthesizer detects missing key metrics from Search output, 
the Coordinator should catch the validation failure and re-invoke the Search agent with a refined query.

## Why I did not use LangGraph or CrewAI?
- The Claude Agent SDK features native subagent orchestration. Unlike standard API clients that require manual message loops, 
the Claude Agent SDK manages memory, runtime states, tool executions, and child subagent delegations dynamically.
- By passing an array of agents into the agent's configuration, you can hand off tasks naturally; Claude spawns a child subagent dynamically, 
runs its tasks isolated with dedicated tools, and returns only the final structured outcome to the supervisor.


## Error Handling and Reliability
To ensure reliable production behavior, implement error handling at two layers:

\- **Tool layer**: Catch external failures such as network errors, timeouts, and parsing issues inside each tool function.  
\- **Orchestration layer**: Let the Coordinator catch sub\-agent failures, log them, and apply structured recovery strategies.
To ensure your multi-agent research system operates reliably in production, you must implement error handling hooks at two distinct layers: inside the tool functions (to catch external network or parsing failures) and at the agent orchestration layer (to allow the coordinator to catch subagent failures, log them, and execute structural recovery strategies).To ensure reliable production behavior, implement error handling at two layers:
