---
phase: 09
phase_name: "approval-bridge-and-compatibility-evidence"
project: "AgentGuard"
generated: "2026-09-04"
language: en
paired_record: 09-LEARNINGS.md
counts:
  decisions: 16
  deliberate_faults: 9
  fixes: 4
  known_limits: 6
---

# Phase 09 Learning Record: Approval Bridge and Compatibility Evidence

This record summarizes behavior that was implemented and observed in tests. It does not turn process-local behavior into a distributed, highly available, or exactly-once guarantee. The paired Chinese record is [09-LEARNINGS.md](./09-LEARNINGS.md).

## 1. Phase Goal and Responsibility Boundary

Phase 9 connects AgentGuard capability policy, recursive redaction, action digests, timeout/retry, resource locks, and audit events to LangGraph's public `interrupt` / `Command(resume=...)` lifecycle. LangGraph remains the sole owner of graph state, the checkpointer, and `thread_id` recovery; AgentGuard owns admission, tool execution, and structured results (D-13, D-16). This phase does not add an external approval service, identity/RBAC, remote persistence, distributed locks, or a frontend UI.

## 2. Design Decisions and Actual Boundaries

### 2.1 Batch Partitioning and One Interrupt (D-01–D-04)

- A batch first executes calls that do not require approval, then combines pending calls into one `interrupt(payload)` (D-01, D-03).
- Pending calls acquire no resource lock before suspension; after resume they pass policy, digest, lock, timeout, retry, and audit boundaries again (D-02).
- A direct-call failure produces a structured failure at its own position and does not prevent sibling calls from entering approval (D-04).
- To avoid repeating direct side effects on resume, the real StateGraph uses separate `prepare` and `approval` nodes. Combining both into one interrupting node must still respect LangGraph replay semantics.

### 2.2 Approval Projection, Redaction, and Binding (D-05–D-08)

The interrupt payload contains stable `batch_id`, `pending_count`, and `payload_version`, plus each call's `tool_call_id`, tool name, recursively redacted argument summary, capabilities, business resource IDs/access modes, and an independent `action_digest` (D-05, D-07, D-08). The projection reuses `redact()` for nested fields; passwords, tokens, secrets, API keys, private keys, and authorization values appear only as `[REDACTED]` markers (D-06). Digests are calculated from canonical, unredacted arguments, so redaction does not weaken the operation binding.

### 2.3 Resume, Partial Approval, and Ordered Results (D-09–D-12)

`Command(resume=...)` decisions are keyed by the original `tool_call_id` and may include `approved`, `actor`, `reason`, and `action_digest` (D-09). A missing decision is a denial; it never becomes implicit approval (D-10). After resume, every original call produces exactly one input-ordered `ToolMessage`; denial, omission, digest mismatch, or a tool missing at resume becomes that call's structured `PermissionDenied`/`UnknownTool` result (D-11). Digests are recomputed from the saved tool name, original arguments, capabilities, `run_id`, and original input index; one mismatch does not cancel siblings (D-12).

### 2.4 Compatibility and Learning Evidence (D-13–D-16)

This release records only the locally verified `langgraph==0.6.11`, `langchain-core==0.3.86`, and Python 3.12.9; it does not promise a historical version matrix (D-13). The fault matrix covers granted, denied, and missing approvals; digest and argument tampering; missing tools at resume; redaction leaks; timeout; retry exhaustion; lock conflicts; and approved-tool failures (D-14). This file and its Chinese pair have matching evidence sections (D-15). Without optional dependencies, adapter-specific tests skip with an explicit `agentguard[langgraph]` installation hint while core tests remain runnable; when installed, real tests do not silently skip (D-16).

## 3. Deliberate Faults, Observations, and Fixes

| Deliberate fault | Observed result | Fix / defense |
|---|---|---|
| Approval explicitly granted | Only the approved tool runs; the result keeps its original ID | Normalize per-call resume decisions, then delegate to Runtime (D-09, D-11) |
| Approval explicitly denied | The corresponding position returns `PermissionDenied`; siblings continue | Fail-closed per-call result handling (D-10, D-11) |
| A decision is missing | The missing item is denied and produces no tool side effect | `normalize_resume_decisions()` (D-10) |
| Digest is replaced | Only the tampered call is denied; other approved calls can run | Recompute from original arguments and input index per call (D-12) |
| Arguments are tampered before resume | Digest mismatch and zero underlying invocations for that call | Preserve the original call and revalidate at the resume boundary (D-05, D-12) |
| Tool disappears before resume | The call returns `UnknownTool`; the batch does not crash | Resolve each tool again during resume (D-11, D-14) |
| Nested password appears in arguments | Interrupt JSON contains `[REDACTED]`, not the password | Reuse recursive `redact()` without copying raw secrets (D-06) |
| Approved tool times out, exhausts retry, conflicts on a lock, or raises | Each receives a structured timeout, retry, resource-lock, or tool failure; siblings are isolated | Reuse Runtime timeout, retry, lock, and failure-isolation boundaries (D-02, D-04, D-14) |
| Interrupt node is replayed | An early single-node design could repeat direct side effects | Use `prepare → approval`; the real test asserts one direct invocation (D-01, D-13) |

## 4. Debugging and Key Fixes

1. **Preserve the original input index.** Once the approved subset is compacted, using its new position would bind the digest to the wrong call. The Runtime batch seam now accepts `step_indices`, so resume continues to use the original index (D-12).
2. **Fix pytest collection collision.** Same-named unit/integration modules caused import-file-mismatch; minimal `tests/unit/__init__.py` and `tests/integration/__init__.py` package markers fixed collection without changing test semantics.
3. **Fix optional-dependency collection boundaries.** Approval unit tests no longer block the core suite when the LangGraph extra is absent; `pytest.importorskip` provides the actionable `agentguard[langgraph]` message (D-16).
4. **Fix replay side-effect risk.** The adapter uses a LangGraph-persisted preparation projection and a separate approval node instead of an in-memory value that is not returned before interrupt. This controls the tested graph composition's at-least-once boundary; it does not claim exactly-once execution (D-01, D-13).

## 5. Test Evidence

On the current worktree (Python 3.12.9, `langgraph 0.6.11`, `langchain-core 0.3.86`) we observed:

- `PYTHONPATH=src pytest -q tests/unit/test_langgraph_approval.py tests/integration/test_langgraph_approval.py tests/integration/test_langgraph_optional.py` → **14 passed**.
- `PYTHONPATH=src pytest -q` → **132 passed**.
- Plan 09-02's additional environment: real approval/optional tests **6 passed**; with optional imports blocked, the core suite reported **91 passed, 12 skipped**, with the reason `install agentguard[langgraph] for LangGraph approval integration tests` (D-13, D-16).

The real StateGraph evidence uses `MemorySaver`, a fixed `configurable.thread_id`, public `Command(resume=...)`, and `interrupt`: suspension happens before the approved tool is invoked; only explicitly approved calls execute after resume; results retain original `tool_call_id` order; and the direct tool is not repeated in this two-node graph (D-01, D-03, D-09, D-11).

## 6. Known Limits and Follow-up Directions

- **At-least-once, not exactly-once:** LangGraph recovery can replay a node. Isolating side effects into the tested preparation/approval structure and making tools idempotent reduces risk, but there is no external transaction or idempotency key here.
- **No identity or RBAC:** `actor` is an audit field in resume data, not proof of authentication or authorization.
- **No external approval UI/service:** The caller consumes the interrupt payload; the project has no remote queue or notification system.
- **No multi-round pending flow:** Missing decisions are denied in this first version; partial decisions do not trigger another interrupt.
- **Process-local locks and state:** There is no cross-process lock, distributed checkpoint, or production HA guarantee.
- **Bounded compatibility:** Evidence applies only to the verified versions and public API combination above, not every historical LangGraph/LangChain release.

## 7. Decision Evidence Index (D-01–D-16)

| Decision | Evidence |
|---|---|
| D-01–D-04 | Prepare/approval, direct-failure, and one-interrupt tests in `tests/unit/test_langgraph_approval.py`; real StateGraph replay test |
| D-05–D-08 | Approval projection unit test, nested-redaction integration test, and stable batch metadata assertions |
| D-09–D-12 | Resume normalization, partial approval, digest mismatch, and missing-tool integration tests |
| D-13 | Version, installation, and StateGraph evidence in `09-COMPATIBILITY.md` |
| D-14 | The fault matrix in Section 3 and the Plan 09-02 test summary |
| D-15 | The matching sections in this file and `09-LEARNINGS.md` |
| D-16 | Optional import skip behavior and the no-extra core-suite result |

---
*Phase: 09-approval-bridge-and-compatibility-evidence*
*Evidence date: 2026-09-04*
