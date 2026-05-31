# What is hook functionality?
- A hook function is a function the framework/library calls for you at a specific lifecycle moment (an “extension point”), 
instead of you calling it directly.
- Think: “When X happens, run my custom logic.”
- Examples of hooks include:
  - `on_tool_error`: Called when a tool execution fails, allowing you to log the error and apply recovery strategies.
  - `before_agent_execution`: Invoked before an agent starts executing, enabling you to modify the input or set up necessary context.
  - `after_agent_execution`: Triggered after an agent finishes executing, allowing you to process the output or clean up resources.
  - `on_subagent_failure`: Called when a sub-agent encounters an error, enabling the coordinator to catch the failure, log it, and decide whether to retry, skip, or abort the workflow.
  - `on_payload_size_exceeded`: Invoked when a payload exceeds a certain size threshold, allowing you to compress the data or split it into smaller chunks before proceeding.
  - `on_token_telemetry`: Triggered when token usage is recorded, enabling you to log token counts and costs for monitoring and optimization purposes.
  - `on_context_update`: Called when the context is updated, allowing you to track changes and ensure that critical information is retained across agent handoffs.
  - `on_execution_timeout`: Invoked when an agent or tool execution exceeds a specified time limit, allowing you to log the timeout and apply fallback strategies.
  - `on_agent_handoff`: Triggered during multi-turn handoffs between agents, enabling you to validate the data being passed and ensure that it adheres to the expected schema and format.
  - `on_agent_completion`: Called when an agent completes its task, allowing you to perform final processing, such as formatting the output or updating a knowledge base.
  - `on_error_recovery`: Invoked when an error recovery strategy is executed, allowing you to log the recovery attempt and its outcome for future analysis and improvement.
  - `on_agent_spawn`: Triggered when a new sub-agent is spawned, enabling you to initialize necessary resources or set up monitoring for that agent's execution.
  - `on_agent_termination`: Called when an agent is terminated, allowing you to clean up resources and log the termination event for auditing purposes.
  - `on_data_validation_failure`: Invoked when data validation fails during an agent's execution, allowing you to log the failure and decide whether to retry with modified input or abort the workflow.
  - `on_external_api_failure`: Triggered when an external API call fails within a tool, enabling you to log the failure and apply retry logic or fallback strategies.
  - `on_resource_limit_exceeded`: Called when an agent or tool exceeds resource limits (such as memory or CPU usage), allowing you to log the event and apply mitigation strategies, such as reducing the workload or scaling resources.
  - `on_agent_idle`: Invoked when an agent remains idle for a certain period, allowing you to log the idle state and decide whether to terminate the agent or prompt it to take action.
  - `on_agent_error`: Triggered when an agent encounters an unexpected error, enabling you to log the error details and apply a structured recovery strategy, such as retrying the task with modified input or escalating the issue to a human operator.
  - `on_agent_success`: Called when an agent successfully completes its task, allowing you to log the success and perform any necessary follow-up actions, such as updating a dashboard or notifying stakeholders.
  - `on_agent_timeout`: Invoked when an agent's execution exceeds a specified time limit, enabling you to log the timeout event and apply fallback strategies, such as retrying the task with a simplified approach or escalating the issue for manual intervention.
  - `on_agent_retry`: Triggered when an agent retries a task after a failure, allowing you to log the retry attempt and its outcome for future analysis and optimization of the retry logic.
  - `on_agent_skip`: Called when an agent decides to skip a task due to certain conditions (such as missing data or low confidence), enabling you to log the skip event and apply alternative strategies, such as invoking a different agent or notifying stakeholders.
  - `on_agent_abort`: Invoked when an agent decides to abort its task due to critical failures or unmet conditions, allowing you to log the abort event and apply necessary cleanup or escalation procedures.
  - `on_agent_log`: Triggered when an agent generates a log message, enabling you to capture and store the log for monitoring and debugging purposes.
  - `on_agent_metric`: Called when an agent records a metric (such as execution time or token usage), allowing you to log the metric and use it for performance monitoring and optimization.
  - `on_agent_checkpoint`: Invoked when an agent reaches a checkpoint in its execution, allowing you to log the checkpoint and use it for tracking progress and debugging.
  - `on_agent_state_change`: Triggered when an agent's state changes (such as transitioning from idle to active), enabling you to log the state change and apply any necessary adjustments to the workflow or resource allocation.
  - `on_agent_memory_update`: Called when an agent updates its memory, allowing you to log the update and ensure that critical information is retained across agent handoffs and executions.
  - `on_agent_context_update`: Invoked when an agent updates its context, enabling you to log the update and ensure that the new context is properly integrated into subsequent agent executions and handoffs.
  - `on_agent_tool_invocation`: Triggered when an agent invokes a tool, allowing you to log the invocation and monitor the usage of different tools across agents for optimization and debugging purposes.
  - `on_agent_subagent_spawn`: Called when an agent spawns a sub-agent, enabling you to log the event and monitor the hierarchy and interactions between agents for better understanding and optimization of the multi-agent system.
  - `on_agent_subagent_termination`: Invoked when a sub-agent is terminated, allowing you to log the event and ensure that any necessary cleanup or follow-up actions are taken for the parent agent and the overall workflow.
  - `on_agent_subagent_error`: Triggered when a sub-agent encounters an error, enabling you to log the error details and apply structured recovery strategies, such as retrying the sub-agent's task with modified input or escalating the issue to the parent agent for further handling.
  - `on_agent_subagent_success`: Called when a sub-agent successfully completes its task, allowing you to log the success and ensure that the parent agent properly integrates the sub-agent's output into the overall workflow.
  - `on_agent_subagent_timeout`: Invoked when a sub-agent's execution exceeds a specified time limit, enabling you to log the timeout event and apply fallback strategies, such as retrying the sub-agent's task with a simplified approach or escalating the issue to the parent agent for manual intervention.
  - `on_agent_subagent_retry`: Triggered when a sub-agent retries a task after

# When to use hook functions
* Use hooks when you need cross-cutting behavior around existing flow:
* Observability: logging, metrics, tracing
* Validation/guardrails: reject bad inputs, enforce limits
* Error handling: retries, fallback logic, cleanup
* Policy/security: permission checks, redaction, audit trail
* Light transformations: normalize payload before next step

**check_synthesizer_tokens_hook(...) is a good example: it intercepts payloads before synthesis and compresses when too large.**

# When NOT to use hooks
* Avoid hooks for core business logic that should be explicit in the main flow. Hooks can make it harder to understand the overall process if too much critical logic is hidden in them.
* Don't use hooks for simple, linear steps that don't require cross-cutting concerns. For example, if you just need to call a tool and process its output, it's clearer to do that directly in the main agent logic rather than abstracting it into a hook.

# Replace AgentRunner with query() (for one-shot tasks) or ClaudeSDKClient (for multi-turn sessions) I did not understand
