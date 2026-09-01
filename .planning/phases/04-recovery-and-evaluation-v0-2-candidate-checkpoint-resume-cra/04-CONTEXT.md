# Phase 4: Recovery and Evaluation (v0.2 candidate) - Context

**Gathered:** 2026-09-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a small, inspectable checkpoint/resume capability and a deterministic evaluation harness to the existing local Python Runtime. The phase covers minimal recoverable state, crash simulation, at-least-once resume semantics, checkpoint validation, recovery evidence, scenario registration, and reliability metrics. Distributed storage, exactly-once execution, semantic model evaluation, and automatic recovery remain out of scope.

</domain>

<decisions>
## Implementation Decisions

### Checkpoint contents and write timing
- **D-01:** Persist only the minimum state required to choose and execute the next Action: `run_id`, `RunState`, current `step`, latest Action/ToolResult context, relevant runtime configuration, and event position/sequence metadata.
- **D-02:** Write a checkpoint after each complete Runtime step: Action chosen, Tool execution finished, result recorded, and step incremented. Use an atomic write boundary.
- **D-03:** The first version explicitly provides at-least-once semantics. If a crash occurs after Tool execution but before checkpoint persistence, resume may execute that Action again.

### Storage and lifecycle
- **D-04:** Use one local JSON checkpoint file per `run_id`, written through a temporary file and atomic replacement.
- **D-05:** Include a `schema_version`; do not introduce Redis, a database, or distributed coordination.
- **D-06:** Retain checkpoint files after completion or terminal failure and update their lifecycle status (`active`, `recoverable`, `completed`, or `failed`). Automatic cleanup is deferred.

### Crash and resume behavior
- **D-07:** Provide deterministic, injectable crash points, especially `after_tool_before_checkpoint`, through a `SimulatedCrash` mechanism that is absent from the normal default path.
- **D-08:** Expose an explicit `resume(checkpoint_path=..., router=...)` API. Normal `run()` must not scan for or automatically resume old checkpoints.
- **D-09:** Resume must validate JSON, required fields, and schema version before executing any Tool. Corrupt, incomplete, or unsupported checkpoints are rejected with distinct errors; the original file remains available for diagnosis.
- **D-10:** Reuse the same logical `run_id` across recovery attempts. Increment `resume_attempt` for each recovery and append events rather than overwriting prior evidence. Mark possible duplicate execution explicitly.

### Evaluation scope
- **D-11:** Measure Runtime reliability only: checkpoint write count/success, recovery success rate, possible duplicate Tool executions, steps from crash to recovery completion, and final-state correctness.
- **D-12:** Implement a small scenario registry shared by tests and benchmark/report generation. Each scenario defines its name, initial state, Router/Tool setup, fault injection, expected terminal state, and metrics.
- **D-13:** Start with three deterministic scenarios: clean completion, Tool-complete/crash-before-checkpoint followed by resume, and corrupt-checkpoint safe rejection.

### the agent's Discretion
The exact JSON field layout, checkpoint filename convention, exception class hierarchy, event names, metric aggregation structure, and test fixture organization are open to standard, inspectable Python approaches as long as the decisions above remain true.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and phase scope
- `.planning/PROJECT.md` — project goals, constraints, and explicit infrastructure exclusions.
- `.planning/REQUIREMENTS.md` — active requirements and definition-of-done expectations.
- `.planning/ROADMAP.md` — Phase 4 recovery/evaluation boundary and dependency on Phase 3.
- `.planning/phases/03-loop-guard-and-reporting/03-CONTEXT.md` — prior Runtime, event, and reporting decisions that Phase 4 must preserve.
- `.planning/phases/03-loop-guard-and-reporting/03-LEARNINGS.md` — verified Phase 3 trade-offs and failure evidence.

### Existing Runtime contracts
- `src/agentguard/domain/state.py` — `RunState`, bounded history, status, and stop-reason model.
- `src/agentguard/domain/runtime.py` — `RunResult` terminal projection.
- `src/agentguard/runtime/engine.py` — sequential Runtime loop and step boundary where checkpoint hooks integrate.
- `src/agentguard/events/model.py` — structured event types and JSON representation.
- `src/agentguard/events/sinks.py` — event sink persistence patterns.
- `src/agentguard/runtime/tool.py` — Tool execution, timeout, cancellation, and retry semantics that resume must preserve.
- `tests/integration/test_runtime_loop.py` — deterministic Router/Tool integration scenarios and fault assertions.

No external specs — requirements are fully captured in the decisions above and the referenced project/phase documents.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RunState` and `HistoryEntry` already provide a bounded, serializable conceptual state window; checkpoint serialization should project this state rather than duplicate the full event log.
- `RuntimeEvent` plus `EventSink` provide the existing append-only evidence path; recovery events should extend these contracts.
- `ToolExecutor` already centralizes timeout and retry behavior, so resume should call the same executor and preserve its safety rules.

### Established Patterns
- Dataclasses with `__post_init__` validation enforce Python-object contracts at boundaries.
- `Runtime.run()` is an async, sequential, single-Action loop with explicit `_finish()` terminal evidence.
- Tests use scripted Routers and deterministic Tools, making crash and recovery scenarios reproducible without a real LLM.

### Integration Points
- Checkpoint hooks belong at the completed-step boundary in `Runtime`.
- `resume()` should reconstruct `RunState` and continue through the same Router/executor path while distinguishing recovery metadata.
- Reporting should consume appended recovery events and expose duplicate-possible and recovery metrics without changing existing V0.1 fields.

</code_context>

<specifics>
## Specific Ideas

- The critical demonstration is a crash in the window `after_tool_before_checkpoint`.
- Recovery is intentionally explicit and inspectable from the filesystem; stale checkpoint files must never trigger an automatic Tool call.
- The first benchmark should be understandable by reading one registered scenario and its JSON result.

</specifics>

<deferred>
## Deferred Ideas

- Exactly-once execution via idempotency keys and durable deduplication.
- Automatic checkpoint discovery and cleanup policies.
- Process-level forced termination and rollback of external side effects.
- Redis/database/distributed checkpoint stores.
- Token, cost, semantic-quality, or real-LLM throughput metrics.
- Parallel scheduling, permission workflows, and framework adapters remain future roadmap work.

</deferred>

---

*Phase: 04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra*
*Context gathered: 2026-09-01*
