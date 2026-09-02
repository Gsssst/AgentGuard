# LangGraph Adapter Architecture Research

## Boundary

```text
LangGraph StateGraph / router / checkpointer
                |
                v
        GuardedToolNode
                |
        AgentGuard Tool + policy
                |
 timeout / retry / permission / lock / audit
                |
          LangChain tool
```

## Proposed flow

1. Read the latest `AIMessage` from the configured messages key.
2. Normalize each call (`name`, `args`, `tool_call_id`) into an AgentGuard `CallTool` action.
3. Resolve a guard by tool name; missing guards produce a denied result without invoking the tool.
4. Partition calls into direct calls and approval-required calls.
5. For approval calls, call LangGraph `interrupt` with redacted call summaries and digests. On resume, validate each decision and digest before execution.
6. Execute approved/direct calls through `Runtime.execute_batch()` or an equivalent adapter-owned execution path.
7. Convert each result to a `ToolMessage` using the original call ID and return the state update expected by LangGraph.

## Ownership

- LangGraph owns graph state, message accumulation, checkpoint persistence, and resume routing.
- AgentGuard owns tool execution policy, failure classification, resource coordination, and audit evidence.
- The adapter translates at the boundary; it must not duplicate checkpoint state or silently bypass Runtime controls.
