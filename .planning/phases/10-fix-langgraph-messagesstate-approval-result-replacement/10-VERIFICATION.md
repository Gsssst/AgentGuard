---
phase: 10-fix-langgraph-messagesstate-approval-result-replacement
verified: 2026-09-04T08:59:00Z
status: passed
score: 9/9 must-haves verified
---

# Phase 10 Verification Report

**Phase Goal:** Eliminate duplicate approval results when `GuardedToolNode` is composed with LangGraph's standard `MessagesState`/`add_messages` reducer, while preserving ordered per-call results and existing adapter compatibility.
**Verified:** 2026-09-04T08:59:00Z
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Pending `prepare()` carries machine state without an approval placeholder | ✓ VERIFIED | `test_pending_prepare_projection_has_no_placeholder_messages` passes and asserts no `messages` key or `ApprovalRequired` content. |
| 2 | `_agentguard_prepared` is the only preparation key and no duplicate boolean is added | ✓ VERIFIED | Adapter implementation and unit projection assertions use the fixed key. |
| 3 | No-pending prepare returns final messages and legacy `__call__()` remains compatible | ✓ VERIFIED | `test_no_pending_prepare_returns_final_messages_directly` and `test_legacy_call_without_approval_remains_compatible` pass. |
| 4 | Approval merges one ordered result per call and consumes pending state | ✓ VERIFIED | Unit approval test asserts IDs/order and `result["_agentguard_prepared"]["pending"] == []`. |
| 5 | Public `prepare()`/`approval()` nodes work with standard `MessagesState + add_messages` | ✓ VERIFIED | Real StateGraph integration uses `graph_api.MessagesState`, `MemorySaver`, and public `Command(resume=...)`. |
| 6 | Mixed direct/approval/denied calls remain isolated and ordered | ✓ VERIFIED | `test_messages_state_add_messages_has_one_ordered_result_per_call_after_resume` passes with three unique ordered IDs. |
| 7 | Direct calls are not replayed across resume | ✓ VERIFIED | Integration assertion keeps direct invocation count at one. |
| 8 | Existing redaction/digest/missing-tool/structured failure behavior remains intact | ✓ VERIFIED | Existing approval integration tests and full suite pass. |
| 9 | Bilingual failure-oriented evidence records the blocker closure and limits | ✓ VERIFIED | `10-LEARNINGS.md` and `10-LEARNINGS.en.md` exist with matching evidence sections. |

**Score:** 9/9 truths verified

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/agentguard/integrations/langgraph.py` | Pending/final state projection fix | ✓ EXISTS + SUBSTANTIVE | Pending branch omits `messages`; approval branch returns final ordered messages and clears pending. |
| `tests/integration/test_langgraph_approval.py` | Real reducer regression | ✓ EXISTS + SUBSTANTIVE | Uses public `MessagesState`, `MemorySaver`, interrupt/resume, mixed calls and exact ID assertions. |
| `tests/unit/test_langgraph_adapter.py` | Projection/compatibility tests | ✓ EXISTS + SUBSTANTIVE | Covers pending omission, no-pending direct output and legacy wrapper. |
| `10-LEARNINGS.md` | Chinese evidence record | ✓ EXISTS + SUBSTANTIVE | Includes B1 reproduction, deliberate faults, tests and limits. |
| `10-LEARNINGS.en.md` | English paired evidence record | ✓ EXISTS + SUBSTANTIVE | Mirrors Chinese structure and claims. |

**Artifacts:** 5/5 verified

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `GuardedToolNode.prepare()` | `_agentguard_prepared` | pending state-only return | ✓ WIRED | `messages` is omitted when pending calls exist. |
| `_agentguard_prepared` | `GuardedToolNode.approval()` | LangGraph state + public interrupt | ✓ WIRED | Approval reads the persisted batch and resumes on the same thread. |
| `approval()` | `MessagesState` | final `ToolMessage` projection | ✓ WIRED | Real reducer test observes one final result per original ID. |
| `Command(resume=...)` | Runtime batch | digest-bound approved subset | ✓ WIRED | Existing approval tests confirm only approved calls execute through Runtime. |

**Wiring:** 4/4 connections verified

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|---|---|---|
| BATCH-04 | ✓ SATISFIED | None; real reducer test proves input order and unique IDs. |
| APPROVAL-03 | ✓ SATISFIED | None; public interrupt/resume and checkpointer path passes. |
| APPROVAL-06 | ✓ SATISFIED | None; mixed batch executes only approved call and returns structured denial. |
| COMPAT-04 | ✓ SATISFIED | None; targeted and full suites cover approval, denial and failure classes. |
| COMPAT-05 | ✓ SATISFIED | None; paired Chinese/English learning records are present. |

**Coverage:** 5/5 plan requirements satisfied

## Anti-Patterns Found

None. No private LangGraph APIs, duplicate checkpoint store, raw secret output, or exactly-once claim was introduced.

## Human Verification Required

None — all Phase 10 acceptance criteria are verifiable programmatically.

## Gaps Summary

**No gaps found.** Phase goal achieved and ready for milestone audit rerun.

## Verification Metadata

**Verification approach:** Goal-backward, based on Phase 10 plan must-haves and v0.3 audit B1.
**Must-haves source:** `10-01-PLAN.md` and `10-02-PLAN.md` frontmatter.
**Automated checks:** 136 passed, 0 failed.
**Human checks required:** 0.
**Total verification time:** 2 min.

---
*Verified: 2026-09-04T08:59:00Z*
*Verifier: primary agent (inline execution fallback)*
