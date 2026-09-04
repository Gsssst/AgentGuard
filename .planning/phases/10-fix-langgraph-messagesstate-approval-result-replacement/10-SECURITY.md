---
phase: 10
slug: fix-langgraph-messagesstate-approval-result-replacement
status: verified
threats_open: 0
asvs_level: 1
created: 2026-09-04
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| LangGraph state → AgentGuard adapter | Checkpointed graph state is read by `prepare()`/`approval()` and must retain the original call identity and digest binding. | Tool names, call IDs, arguments, capabilities, resource metadata, digests |
| Approval interrupt → adapter | Resume data is untrusted input and is normalized fail-closed before any approved call is dispatched. | Approval decisions, actor/reason fields, action digests |
| AgentGuard adapter → Runtime | Only validated, guarded calls cross into Runtime batch execution; direct and approved calls retain their input indexes. | `CallTool`, typed `Tool`, run ID, per-call approval context |
| Adapter → LangGraph `MessagesState` | Final results cross the reducer boundary as ordered `ToolMessage` values; pending placeholders are kept out of the message projection. | Safe result values or structured error summaries |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-10-01 | Tampering | `_agentguard_prepared` state | mitigate | Preserve original arguments, run ID, input index, capabilities, and digest; recompute and compare the digest before approval dispatch. (`langgraph.py:265-295`, `338-345`) | closed |
| T-10-02 | Information disclosure | Pending state/message projection | mitigate | Approval payloads use recursive redaction; pending `prepare()` emits no placeholder message and error content uses safe summaries. (`approval.py:149-184`, `langgraph.py:291-295`, `langgraph.py:49-74`) | closed |
| T-10-03 | Repudiation | Result/message correlation | mitigate | Build final output by input index, preserve each original `tool_call_id`, and represent failures with typed structured fields. (`langgraph.py:248-257`, `365-382`) | closed |
| T-10-04 | Denial of service | Stale approval route | mitigate | Approval completion clears `pending` and pending calls acquire no Runtime resource lock during the interrupt wait. (`langgraph.py:148-150`, `397-399`) | closed |
| T-10-05 | Tampering | Persisted LangGraph state/resume | mitigate | Resume is bound to the persisted batch, same thread/checkpoint, and per-call digest; malformed or mismatched approvals fail closed. (`approval.py:187-245`, `langgraph.py:307-345`) | closed |
| T-10-06 | Information disclosure | Interrupt and learning evidence | mitigate | Human-facing arguments are redacted, while raw exception stacks and sensitive values are excluded from `ToolMessage` error summaries; integration test asserts the secret is absent. (`approval.py:167-179`, `langgraph.py:49-74`, `test_langgraph_approval.py:131-136`) | closed |
| T-10-07 | Repudiation | Duplicate/missing result correlation | mitigate | Duplicate call IDs are rejected before dispatch; real `MessagesState` integration asserts exactly one ordered result per original ID after resume. (`langgraph.py:172-194`, `test_langgraph_approval.py:189-240`) | closed |
| T-10-08 | Availability | Replayed direct side effects | mitigate | Split `prepare`/`approval` nodes execute direct work once before interruption; the integration test asserts no replay and documents LangGraph at-least-once limits. (`langgraph.py:131-150`, `test_langgraph_approval.py:105-110`, `239-240`) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

## Accepted Risks Log

No accepted risks. LangGraph checkpoint durability and its at-least-once resume semantics remain external framework behavior; this phase documents and tests the adapter boundary but does not claim exactly-once side effects.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-04 | 8 | 8 | 0 | primary agent (inline security audit) |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-04

