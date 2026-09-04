# Phase 10: Fix LangGraph MessagesState approval result replacement - Pattern Map

**Mapped:** 2026-09-04  
**Files analyzed:** 6 implementation/test/evidence files  
**Analogs found:** 6 / 6

## File Classification

| File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/agentguard/integrations/langgraph.py` | adapter/orchestrator | LangGraph state → Runtime batch → message projection | same file, `GuardedToolNode.prepare()` / `approval()` | exact |
| `src/agentguard/integrations/approval.py` | DTO/normalizer | interrupt payload ↔ resume decisions | same file, `ApprovalBatch` / `normalize_resume_decisions()` | exact |
| `tests/unit/test_langgraph_adapter.py` | deterministic adapter tests | fake AI/tool messages → assertions | existing multi-tool and failure tests | exact |
| `tests/integration/test_langgraph_approval.py` | real graph integration | `StateGraph` + checkpointer + `Command(resume=...)` | existing approval tests | exact |
| `.planning/v0.3-INTEGRATION-AUDIT.md` | audit/evidence | observed reducer behavior → acceptance target | B1 reproduction section | exact |
| `.planning/phases/09-approval-bridge-and-compatibility-evidence/09-CONTEXT.md` | decision contract | approval/replay/ordering constraints | D-01..D-16 | exact |

## Pattern Assignments

### `src/agentguard/integrations/langgraph.py`

- Keep the current per-call validation and `Runtime.execute_explicit_batch()` seam. The defect is in the node return projection, not in permission, digest, locking, timeout, or retry behavior.
- For a pending batch, return `_agentguard_prepared` with JSON-safe `pending`, `immediate`, `calls_count`, `run_id`, and approval batch data, but omit the `messages` key entirely. Omitting the key lets the existing `messages` state remain unchanged through `add_messages`.
- For a no-pending batch, retain the existing `{"messages": output}` result. The conditional route can therefore inspect only `_agentguard_prepared.pending`.
- On approval completion, return one final ordered `ToolMessage` per input index and mark the prepared context consumed (for example, an empty `pending` list) so a caller-owned route cannot re-enter approval from stale state.
- Preserve `__call__()` as a compatibility wrapper around `prepare()` and `approval()`; do not introduce a second node abstraction.

### `tests/unit/test_langgraph_adapter.py`

- Reuse existing fake `AIMessage`/LangChain tool fixtures and JSON assertions.
- Add focused assertions for the projection contract: pending `prepare()` has no user-visible placeholder messages, no-pending `prepare()` returns final messages, and ordinary `__call__()` remains source-compatible.
- Keep tests deterministic and avoid a real LLM or external service.

### `tests/integration/test_langgraph_approval.py`

- Reuse `MemorySaver`, public `StateGraph`, `START`/`END`, `Command`, and the existing `RecordingTool` fake.
- Define a state based on the public `MessagesState` reducer while adding only the `_agentguard_prepared` machine key required by the two-node composition.
- Use a mixed input batch with direct, approval-required, and denied calls. Inspect the paused checkpoint-visible state before resume and the final `ToolMessage` list after resume.
- Assert by `tool_call_id`, not by message text or list position alone; retain the input index order for direct/approved/denied results.

### Evidence and safety patterns

- The audit's B1 reproduction is the failure oracle: paused state must not contain an `ApprovalRequired` placeholder, and resumed state must not contain duplicate IDs.
- Continue fail-closed structured error messages and recursive redaction. No raw exception detail, secret argument, private LangGraph import, or AgentGuard checkpoint store belongs in this fix.

