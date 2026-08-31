# Phase 1: Deterministic Runtime Skeleton - Context

**Gathered:** 2026-08-31
**Status:** Ready for planning

## Phase Boundary

Build the smallest deterministic Agent Runtime skeleton: a state-driven router, one-action-per-turn execution, explicit run termination, structured events, and a local CLI path. Timeout, retry, loop detection, and parallel scheduling are not implemented in this phase.

## Confirmed Decisions

### Agent loop

- Use a LangGraph-like `State + Router` model.
- The router receives current `RunState` and proposes the next step.
- V0.1 first implements a small project-owned router abstraction rather than depending directly on LangGraph.
- A future LangGraph adapter may implement the same boundary.
- Router decision and Runtime permission/execution remain separate responsibilities.

### Tool execution

- Support both synchronous and asynchronous Tool callables.
- Expose one asynchronous Runtime execution entry point.
- Async tools are awaited directly; sync tools will be adapted internally.
- V0.1 executes at most one Action per router turn and uses sequential execution.
- Parallel multi-tool scheduling is deferred until a later concurrency phase.
- The design must make the weaker cancellation semantics of adapted sync tools visible rather than implying that timeout always stops underlying side effects.

### Events and persistence

- Treat Events as structured runtime logs: facts about what happened, not the full resumable state.
- Decouple event production from storage through a small `EventSink` interface.
- V0.1 implements `InMemoryEventSink` for tests and `JsonlEventSink` for CLI runs.
- Checkpointing is deferred, but `RunState` should not be designed in a way that prevents a later checkpoint/resume implementation.

### Runtime state

- `RunState` contains the current decision-making state rather than the complete audit history.
- Minimum fields are `run_id`, `step`, `status`, `last_result`, and a bounded recent history.
- The initial recent-history window is 10 steps; the complete event stream remains in the configured `EventSink`.

### Actions

- Use typed Python objects rather than unconstrained dictionaries for V0.1 actions.
- `CallTool(tool_name, arguments)` requests one tool execution.
- `Finish(reason)` requests explicit run completion.
- The router returns at most one Action per turn.
- V0.1 does not include approval, parallel-call, delegation, or context-update actions; those belong to later phases.

### Tool results

- Tools may return normally or raise exceptions, but the Runtime converts both paths into a typed `ToolResult` before updating `RunState`.
- Phase 1 result statuses are `SUCCESS` and `FAILED`; timeout and cancellation statuses are added with their actual Phase 2 semantics.
- Result errors use serializable `error_type` and `error_message` fields rather than retaining raw exception objects.
- Tracebacks belong to diagnostic logging and are not part of the default structured event payload.

## Open Decisions

- Event sink and persistence model.
- Exact Phase 1 Action, RunState, Tool, Result, and StopReason shapes.
- CLI command shape and baseline acceptance tests.

## Learning Questions

- What state is necessary for routing without coupling the router to storage?
- Which event fields are required to reconstruct one run?
- How should sync-tool adaptation and cancellation limits be demonstrated?

---
*Phase: 01-deterministic-runtime-skeleton*
*Context gathered: 2026-08-31*
