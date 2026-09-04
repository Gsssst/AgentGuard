---
phase: 09-approval-bridge-and-compatibility-evidence
verified: 2026-09-04T01:19:22Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 9: Approval Bridge and Compatibility Evidence Verification Report

**Phase Goal:** Bridge AgentGuard approval semantics to LangGraph `interrupt/resume`, validate digests, and finish real/fake compatibility evidence and bilingual learning notes.
**Verified:** 2026-09-04T01:19:22Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Approval-required calls pause before invocation with one LangGraph interrupt carrying a redacted, versioned projection. | ✓ VERIFIED | `GuardedToolNode.prepare()` partitions calls and `approval()` calls public `langgraph.types.interrupt` once; real StateGraph test observes one interrupt and zero pending-tool invocations while paused. |
| 2 | The interrupt projection contains independent call IDs, capabilities, resource summaries, and per-call digests without raw secrets. | ✓ VERIFIED | `build_approval_batch()` uses canonical unredacted arguments for `action_digest()` and existing recursive `redact()` for payload arguments; unit and integration tests assert nested password/token masking and stable batch IDs. |
| 3 | `Command(resume=...)` on the same `configurable.thread_id` resumes through LangGraph checkpoint state. | ✓ VERIFIED | `tests/integration/test_langgraph_approval.py` compiles public `StateGraph` with `MemorySaver`, pauses, then resumes with public `Command(resume=...)` and the same thread ID. |
| 4 | Approval decisions are independent, keyed by `tool_call_id`, and fail closed for missing, malformed, unknown, or denied entries. | ✓ VERIFIED | `normalize_resume_decisions()` and partial/missing decision tests show only explicit valid approvals execute; missing decisions become `PermissionDenied` while siblings remain processable. |
| 5 | Resume recomputes the digest from original arguments, capabilities, run ID, and input index; tampering isolates to the affected call. | ✓ VERIFIED | `approval()` reconstructs original `CallTool` from the persisted preparation context, recomputes `action_digest`, and tests cover mismatched digest and argument tampering with zero invocation for the tampered call. |
| 6 | Only approved calls execute through Runtime boundaries; every original call returns one ordered `ToolMessage` with its original ID. | ✓ VERIFIED | Approved subset is sent to `Runtime.execute_explicit_batch()` with approval context and original `step_indices`; unit/real graph tests assert ordered IDs, partial approval, and structured denials. |
| 7 | Failure isolation and runtime controls remain active after approval. | ✓ VERIFIED | Deterministic tests cover direct failure, timeout, retry exhaustion, resource-lock conflict, missing tool, and post-approval failure; `asyncio.gather()` returns per-call results without cancelling unrelated calls. |
| 8 | Compatibility behavior is bounded to the verified optional stack and optional tests skip clearly when dependencies are absent. | ✓ VERIFIED | `pyproject.toml` pins `langgraph==0.6.11` and `langchain-core==0.3.86`; current targeted suite runs 27 tests, full suite runs 132 tests, and the no-extra subprocess confirms core importability plus an actionable `agentguard[langgraph]` adapter error. |
| 9 | Chinese and English learning records document decisions, deliberate faults, fixes, test evidence, and limits. | ✓ VERIFIED | `09-LEARNINGS.md`, `09-LEARNINGS.en.md`, and `09-COMPATIBILITY.md` are non-empty, paired, and enumerate D-01–D-16, fault scenarios, commands/results, bounded versions, and at-least-once limitations. |

**Score:** 9/9 truths verified

### Decision Coverage (D-01–D-16)

| Decisions | Status | Evidence |
|---|---|---|
| D-01–D-04 | ✓ VERIFIED | `prepare` executes direct calls before a single approval stage; direct failures are retained in-place; real replay test proves direct call count remains one in the two-node graph. |
| D-05–D-08 | ✓ VERIFIED | Versioned `ApprovalBatch`, recursive redaction, business resource ID/access projection, stable `batch_id`, and per-call digest assertions. |
| D-09–D-12 | ✓ VERIFIED | Per-ID normalization, missing-as-deny behavior, ordered complete output, independent digest recomputation and mismatch isolation. |
| D-13 | ✓ VERIFIED | Public StateGraph/MemorySaver/interrupt/Command APIs tested on Python 3.12.9, LangGraph 0.6.11, LangChain Core 0.3.86; compatibility note makes bounded claims only. |
| D-14 | ✓ VERIFIED | Fault matrix tests cover grant, reject, omission, digest/argument tamper, missing tool, redaction, timeout, retry exhaustion, lock conflict, and tool failure. |
| D-15 | ✓ VERIFIED | Chinese and English records have matching evidence sections and explicit known limits. |
| D-16 | ✓ VERIFIED | Optional modules use narrow `importorskip` with install guidance; no-extra core import remains runnable and installed-path tests execute. |

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/agentguard/integrations/approval.py` | Typed approval payload and fail-closed resume helpers | ✓ VERIFIED | Substantive frozen DTOs, stable ID/digest projection, recursive redaction and normalization implementation. |
| `src/agentguard/integrations/langgraph.py` | Public LangGraph interrupt/resume bridge | ✓ VERIFIED | `GuardedToolNode.prepare()`/`approval()` and ordered Runtime execution path are implemented and exercised. |
| `src/agentguard/runtime/engine.py` | Approval-aware explicit batch execution | ✓ VERIFIED | `execute_explicit_tool/batch` recheck permission and digest, emit audit events, acquire locks only at execution time, and preserve original step indexes. |
| `tests/unit/test_langgraph_approval.py` | Deterministic approval/fault coverage | ✓ VERIFIED | 7 approval-specific tests collected and passed. |
| `tests/integration/test_langgraph_approval.py` | Real StateGraph/checkpointer evidence | ✓ VERIFIED | 3 real interrupt/resume tests collected and passed. |
| `tests/integration/test_langgraph_optional.py` | Optional API/version evidence | ✓ VERIFIED | Public API, exact-version, and real adapter tests collected and passed. |
| `pyproject.toml` | Bounded optional dependency declaration | ✓ VERIFIED | Exact verified pins for LangGraph and LangChain Core. |
| `09-LEARNINGS.md`, `09-LEARNINGS.en.md`, `09-COMPATIBILITY.md` | Bilingual evidence and compatibility record | ✓ VERIFIED | Concrete commands, observed results, fault matrix, decisions, and limitations; no placeholders. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `GuardedToolNode.approval` | `langgraph.types.interrupt` / `Command(resume=...)` | One interrupt payload and resume value | ✓ WIRED | Source imports public `interrupt`; real tests resume compiled graph with public `Command`. |
| `approval.py` | `runtime.permission` | `redact()` and `action_digest()` | ✓ WIRED | Direct imports and calls are present; tests distinguish masked projection from unredacted digest. |
| `GuardedToolNode` | `Runtime.execute_explicit_batch` | Preparation and post-resume approved subset | ✓ WIRED | Both direct and approved paths call Runtime explicit batch; approved path passes approval context and original step indices. |
| Real integration graph | `MemorySaver` + `configurable.thread_id` | LangGraph-owned checkpoint/recovery | ✓ WIRED | `_graph()` compiles with `MemorySaver`; pause/resume uses identical thread ID and passes in current environment. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `GuardedToolNode` | `ToolMessage.content` | `Runtime.execute_explicit_batch` / structured failure constructors | Yes — actual fake tools and Runtime failure results | ✓ FLOWING |
| Approval projection | `items[*].arguments` | Original `CallTool.arguments` passed through existing `redact()` | Yes — nested secret tests observe redaction markers | ✓ FLOWING |
| Resume execution | Approved tool result | `Command(resume=...)` decision map → Runtime explicit execution | Yes — real StateGraph test observes tool side effect once | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full source-tree behavior | `PYTHONPATH=src pytest -q` | `132 passed in 0.93s` | ✓ PASS |
| Approval and real integration behavior | `PYTHONPATH=src pytest -q tests/unit/test_langgraph_adapter.py tests/unit/test_langgraph_approval.py tests/integration/test_langgraph_optional.py tests/integration/test_langgraph_approval.py -rs` | `27 passed` | ✓ PASS |
| Core import without optional packages | `PYTHONPATH=src python -S -c 'import agentguard'` | `core-import-ok` | ✓ PASS |
| Adapter import without optional packages | `PYTHONPATH=src python -S -c 'import agentguard.integrations.langgraph'` | Non-zero with actionable `agentguard[langgraph]` message | ✓ PASS |
| Public API/static hygiene | `python -m compileall -q src tests; git diff --check` | Both passed; no private LangGraph imports or debt markers in phase files | ✓ PASS |

## Probe Execution

No phase probe scripts were declared or discovered under `scripts/*/tests/probe-*.sh`; probe execution is not applicable.

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| APPROVAL-01 | 09-01 | Pause before approved tool invocation | ✓ SATISFIED | Real interrupt test and adapter implementation. |
| APPROVAL-02 | 09-01 | Redacted summary, call ID, digest | ✓ SATISFIED | Projection and nested redaction tests. |
| APPROVAL-03 | 09-01 / 09-02 | Command resume and LangGraph-owned checkpoint | ✓ SATISFIED | MemorySaver/thread ID StateGraph tests. |
| APPROVAL-04 | 09-01 | Independent per-call decisions | ✓ SATISFIED | Normalization and partial approval tests. |
| APPROVAL-05 | 09-01 / 09-02 | Digest mismatch rejects changed calls | ✓ SATISFIED | Digest and argument tamper tests. |
| APPROVAL-06 | 09-01 / 09-02 | Approved execution and structured denials | ✓ SATISFIED | Ordered ToolMessage assertions and Runtime seam. |
| COMPAT-03 | 09-02 | Installed tests run; absent extra skips clearly | ✓ SATISFIED | Optional tests and no-extra import spot-check. |
| COMPAT-04 | 09-02 | Success/denial/timeout/retry/lock/approval/digest matrix | ✓ SATISFIED | 27 targeted and 132 full tests pass. |
| COMPAT-05 | 09-03 | Bilingual learning notes with failures and limits | ✓ SATISFIED | Paired learning records and compatibility note. |

The roadmap's additional BATCH-01–05 entries are implemented by Phase 8 and are outside this phase's requirement set; no Phase 9 orphaned requirement was found.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| — | — | None found in phase implementation or evidence files | — | No unreferenced TODO/FIXME/TBD/XXX markers, placeholder implementations, or private LangGraph imports detected. |

## Human Verification Required

None. The phase has no visual UI, external service, or performance-feel criterion; the bounded compatibility behavior is covered by executable tests. The documented at-least-once limitation remains explicit and is not treated as exactly-once.

## Gaps Summary

No blocking gaps found. Phase 9 goal is achieved for the declared bounded scope. The evidence intentionally does not promise exactly-once side effects, external approval UI/services, reviewer authentication/RBAC, distributed locks/checkpoints, multi-round pending approvals, or an unrestricted historical LangGraph version matrix. The first isolated clean install could not download `setuptools>=68` in the network-restricted sandbox; the compatibility note records that limitation and a successful local fallback, so this is an environment constraint rather than an implementation gap.

---

_Verified: 2026-09-04T01:19:22Z_  
_Verifier: gsd-verifier agent_
