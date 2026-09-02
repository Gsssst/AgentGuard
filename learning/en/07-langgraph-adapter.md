# Phase 7 Learning Note: LangGraph Adapter

This phase adds the foundation `GuardedToolNode`. LangGraph remains the owner of graph state and checkpointing; AgentGuard owns permission, timeout, retry, resource-lock, and audit boundaries. The adapter keeps its own tool registry and invokes `Runtime.execute_explicit_tool()` without mutating the Runtime's global registry.

## Failure experiments

- A tool without `ToolGuard` is not invoked and returns a structured denial message.
- Missing messages or tool calls return structured failure messages instead of uncaught exceptions.
- Async tools use `ainvoke()` first; synchronous tools use a worker-thread fallback.
- `ToolMessage` preserves the original `tool_call_id`; non-string results use stable JSON serialization.

## Evidence

- `PYTHONPATH=src pytest -q tests/unit/test_runtime_explicit_tool.py`: 4 passed.
- `PYTHONPATH=src pytest -q tests/unit/test_langgraph_adapter.py`: 4 passed.
- After installing `langgraph 0.6.11` and `langchain-core 0.3.86`, the real message round-trip smoke test passed.
- Full suite: 103 passed.

## Known limits

This phase handles one tool call only. Multi-call concurrency is Phase 8, and `interrupt/resume` approval bridging is Phase 9. Distributed locks, a full graph factory, and automatic capability inference remain out of scope.
