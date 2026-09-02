# Phase 7: GuardedToolNode Foundation - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-09-02
**Phase:** 7-GuardedToolNode Foundation
**Areas discussed:** Node input and output shape, LangChain Tool invocation, AgentGuard Runtime injection

## Node input and output shape

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable messages key | Default `state["messages"]`, configurable `messages_key` | ✓ |
| Fixed messages key | Only `state["messages"]` | |
| Explicit message argument | Caller passes an `AIMessage` directly | |

**User's choice:** Configurable messages key
**Notes:** Return `{"messages": [...]}`; missing/empty input becomes a structured failure; process the last AI message with tool calls.

## LangChain Tool invocation

| Option | Description | Selected |
|--------|-------------|----------|
| Async-first fallback | Prefer `.ainvoke()`, fallback to threaded `.invoke()` | ✓ |
| Threaded sync only | Always call `.invoke()` in a worker thread | |
| Async-only | Require `.ainvoke()` | |

**User's choice:** Async-first fallback
**Notes:** Preserve strings, stable-JSON serialize other JSON values, and expose safe error summaries only.

## AgentGuard Runtime injection

| Option | Description | Selected |
|--------|-------------|----------|
| Inject configured Runtime | Caller supplies the Runtime | ✓ |
| Create Runtime internally | Node builds its own Runtime | |
| Inject or create | Runtime injection preferred, otherwise auto-create | |

**User's choice:** Inject configured Runtime
**Notes:** Adapter-owned registry; no Runtime global mutation; name conflicts are configuration errors; run ID from `RunnableConfig` or generated, step from call index.

## the agent's Discretion

- Exact module/class naming adjacent to the locked `GuardedToolNode` and `ToolGuard` concepts.
- Exact safe error payload and supported dependency version range after verification.

## Deferred Ideas

- Multi-tool batch execution — Phase 8.
- Approval interrupt/resume — Phase 9.
- Graph factory, streaming, DAG, and distributed coordination — future scope.
