# v0.3 LangGraph Adapter Research Summary

## Recommendation

Build a thin `GuardedToolNode` adapter around public LangGraph/LangChain Core APIs. Keep LangGraph's graph state, checkpoint, and interrupt lifecycle authoritative; route every actual tool invocation through AgentGuard's existing policy and execution boundaries.

## Stack additions

- Optional `langgraph` and `langchain-core` extra.
- Public APIs: `ToolNode`-compatible state shape, `AIMessage.tool_calls`, `ToolMessage`, `interrupt`, and `Command(resume=...)`.
- Exact versions remain to be verified in implementation because the dependencies are not installed in the current environment.

## Scope priorities

1. Single-call guarded execution and structured failures.
2. Multiple calls with input-order results and independent failure handling.
3. Approval bridge using interrupt/resume and digest validation.
4. Documentation, bilingual learning notes, and deterministic integration tests.

## Main risks

Message shape/version drift, duplicated checkpoint state, lost tool-call IDs, unsafe approval resume, and accidental execution of unconfigured tools.
