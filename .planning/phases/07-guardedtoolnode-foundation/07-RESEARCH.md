# Phase 7: GuardedToolNode Foundation - Research

**Researched:** 2026-09-02
**Research mode:** Local codebase and public API contract review

## Existing seam

`Runtime.run()` and `Runtime.execute_batch()` currently resolve tools from the injected `ToolExecutor` registry. Phase 7 decisions require an Adapter-owned registry that must not mutate that global registry, so the implementation needs a narrow explicit-tool execution seam. The seam should accept a `CallTool` plus an already normalized AgentGuard `Tool`, then reuse Runtime's permission, resource-lock, timeout, retry, and event behavior.

## External API assumptions

- LangGraph nodes receive state and optional `RunnableConfig` and return a state update.
- LangChain messages expose `AIMessage.tool_calls`; tool results use `ToolMessage` with `tool_call_id`.
- `langgraph.prebuilt.ToolNode` is the behavioral reference for node input/output, but the adapter should use public message and interrupt APIs only.
- LangGraph and LangChain Core are not installed in the current environment, so exact versions and constructor signatures must be verified during implementation in an optional-dependency environment.

## Recommended implementation order

1. Add the Runtime explicit-tool execution seam without changing existing `run()` and `execute_batch()` behavior.
2. Add lazy optional imports, `ToolGuard`, LangChain-tool normalization, and single-call message translation.
3. Add fake-message/fake-tool tests and packaging checks; add real LangGraph tests behind an import skip.

## Risks to address in plans

- A failed optional import must not break `import agentguard`.
- Adapter must preserve the original `tool_call_id` and never invoke an unconfigured tool.
- Safe message content must not leak stack traces or unredacted sensitive arguments.
- Sync fallback must remain in a worker thread and use the existing timeout semantics.
