# Phase 7: GuardedToolNode Foundation - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Add the optional LangGraph/LangChain dependency boundary, normalize LangChain tools into AgentGuard metadata, and implement a `GuardedToolNode` single-call path that uses the existing AgentGuard permission, timeout, retry, resource-lock, and audit boundaries. Multi-tool batching belongs to Phase 8; approval interrupt/resume belongs to Phase 9.

</domain>

<decisions>
## Implementation Decisions

### Node input and output shape
- **D-01:** Read messages from `state["messages"]` by default and support a configurable `messages_key`.
- **D-02:** Return a state update shaped as `{"messages": [ToolMessage, ...]}` so LangGraph reducers can append results.
- **D-03:** Missing or empty messages return a structured failure message instead of raising or silently returning an empty update.
- **D-04:** Process only the last `AIMessage` that contains `tool_calls`; do not rescan historical messages.

### LangChain Tool invocation
- **D-05:** Prefer a tool's async `.ainvoke()` method; fall back to synchronous `.invoke()` in a worker thread.
- **D-06:** Pass `tool_call["args"]` through unchanged and let the LangChain tool schema validate it.
- **D-07:** Preserve string results; serialize other JSON-compatible results to stable JSON strings for `ToolMessage.content`.
- **D-08:** Expose only a stable safe error summary to the Agent; keep detailed exceptions in AgentGuard events/reports.

### Runtime and registry ownership
- **D-09:** Require callers to inject an already configured AgentGuard `Runtime`.
- **D-10:** Convert LangChain tools at adapter initialization into an Adapter-owned AgentGuard registry; do not mutate the Runtime's global registry or create a per-call executor that bypasses Runtime controls.
- **D-11:** Detect same-name conflicts between Adapter and Runtime tools and raise a configuration error rather than silently overriding either side.
- **D-12:** Read an optional `run_id` from `RunnableConfig`; otherwise generate a unique node invocation ID. Use the current call index as the digest/event step.

### the agent's Discretion
- Exact public class/module names adjacent to `GuardedToolNode` and `ToolGuard`, provided the locked behavior above is preserved.
- Exact safe error content schema and JSON serialization details, provided IDs, failure kind, and audit safety remain stable.
- Supported LangGraph/LangChain Core version range, after clean-environment verification.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and milestone scope
- `.planning/PROJECT.md` — current milestone goals, constraints, and locked adapter direction.
- `.planning/REQUIREMENTS.md` — ADAPTER and COMPAT requirements for Phase 7.
- `.planning/ROADMAP.md` — Phase 7 goal, dependencies, and success criteria.
- `.planning/research/SUMMARY.md` — LangGraph public API recommendations and integration risks.
- `.planning/research/ARCHITECTURE.md` — ownership boundary between LangGraph and AgentGuard.
- `.planning/research/PITFALLS.md` — message ID, checkpoint, optional dependency, and error-handling pitfalls.

### Existing AgentGuard implementation
- `src/agentguard/runtime/engine.py` — Runtime permission, lock, tool execution, batch, and event boundaries.
- `src/agentguard/runtime/tool.py` — Tool metadata, registry, and async/sync execution semantics.
- `src/agentguard/runtime/permission.py` — capability decisions, redaction, and action digest helpers.
- `src/agentguard/domain/actions.py` — `CallTool` action contract.
- `src/agentguard/domain/results.py` — `ToolResult`, status, and failure-kind contracts.
- `src/agentguard/events/model.py` — event types and stable event representation.

### External specifications
- LangGraph/LangChain documentation was summarized in `.planning/research/STACK.md`; exact dependency versions remain unverified until optional packages are installed in a clean environment.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Tool`, `ToolRegistry`, and `ToolExecutor` provide the metadata and invocation boundary to wrap LangChain tools.
- `Runtime.run()` already enforces permission, timeout, retry, resource lock, and event semantics.
- `redact`, `action_digest`, and `ToolResult` support safe result conversion and evidence binding.

### Established Patterns
- Dataclasses validate inputs in `__post_init__` and expose immutable contracts.
- Unknown tools and execution failures are represented as typed results rather than uncaught runtime errors.
- Sync callables run in worker threads while async callables are awaited through one async boundary.

### Integration Points
- Add a lazy optional-dependency adapter module under `src/agentguard/integrations/` (or an equivalent isolated package path).
- Keep core package imports free of LangGraph imports; expose adapter symbols only through a guarded/lazy path.
- Add unit tests with fake LangChain-compatible tools/messages and optional real integration tests that skip clearly when dependencies are absent.

</code_context>

<specifics>
## Specific Ideas

- The public usage should feel like replacing a normal LangGraph `ToolNode` with `GuardedToolNode` while retaining the existing graph routing.
- LangGraph owns graph state and checkpointing; AgentGuard is the execution guard, not a second graph runtime.
- Failure messages should be useful to the Agent without exposing stack traces or sensitive arguments.

</specifics>

<deferred>
## Deferred Ideas

- Multi-tool-call batch concurrency and ordered result aggregation — Phase 8.
- LangGraph `interrupt/resume` approval bridge and digest-bound independent decisions — Phase 9.
- Full graph factory, streaming progress, DAG scheduling, distributed locks, and broad framework-neutral adapters — future milestones.

</deferred>

---

*Phase: 7-GuardedToolNode Foundation*
*Context gathered: 2026-09-02*
