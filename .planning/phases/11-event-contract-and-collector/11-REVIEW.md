---
phase: 11-event-contract-and-collector
reviewed: 2026-09-06T14:13:53Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - src/agentguard/__init__.py
  - src/agentguard/_safety.py
  - src/agentguard/events/__init__.py
  - src/agentguard/events/collector.py
  - src/agentguard/events/contract.py
  - src/agentguard/events/normalize.py
  - src/agentguard/integrations/langgraph.py
  - src/agentguard/runtime/engine.py
  - src/agentguard/runtime/permission.py
  - tests/integration/test_event_correlation.py
  - tests/integration/test_langgraph_observability.py
  - tests/unit/test_event_collector.py
  - tests/unit/test_event_contract.py
  - tests/unit/test_event_safety.py
findings:
  critical: 8
  warning: 2
  info: 0
  total: 10
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-09-06T14:13:53Z  
**Depth:** standard  
**Files Reviewed:** 14  
**Status:** issues_found

## Summary

The changed event boundary, collector, Runtime correlation paths, LangGraph adapter, and their tests were reviewed adversarially. The submitted suite is green (`212 passed`), but it does not cover several contract-bypass and hostile-input paths. Eight blockers can disclose values, crash an Agent/graph, lose observability, corrupt logical-call grouping, or leave run summaries in a false state. Two additional robustness defects should also be fixed.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Public envelope decoding accepts unredacted and unbounded preview values

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/events/contract.py:170-175` (reached through `from_dict` at lines 633-667)  
**Issue:** `_preview()` checks only the wrapper keys, a boolean flag, and generic JSON compatibility. It does not enforce the projector's depth, width, node, or string limits, and it does not reject/redact sensitive keys. Therefore `EventEnvelope.from_dict()` accepts a payload such as `arguments={"value":{"password":"PLAINTEXT"},"truncated":false}` and returns an envelope that serializes the plaintext. A caller can also submit arbitrarily large/deep JSON under `value`. This bypasses the very safety boundary downstream persistence and streaming are expected to trust.

**Fix:** Validate decoded previews with the same structural invariants as `safe_preview`, and fail closed if the supplied value is not already a canonical safe projection. Prefer a single canonical `SafePreview.from_untrusted()`/decoder that verifies bounds, sensitive-key masking, placeholders, and the truthfulness of `truncated`; use it from both `NormalizedEvent` and `EventEnvelope.from_dict()`.

### CR-02: Truncating a key before sensitivity matching leaks values from long sensitive keys

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/_safety.py:126-140`  
**Issue:** `_visit_mapping()` projects/truncates a key first and then runs `_is_sensitive()` on the truncated key. If a marker appears after character 512 (for example, `"x" * 512 + "password"`), the marker is removed and the value is traversed in plaintext. This was reproduced with `safe_preview({long_password_key: "LEAK"})`; the serialized preview contained `LEAK`.

**Fix:** Test sensitivity against the original validated string key before applying output-key truncation. Also define a deterministic collision policy for keys that truncate to the same output string so a later value cannot silently replace earlier evidence.

### CR-03: A custom Mapping can execute code and abort Runtime during redaction

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/_safety.py:98-100,117-142`  
**Issue:** The projector treats every `collections.abc.Mapping` as safe to iterate and invokes its user-defined `items()`. A nested `dict` subclass whose `items()` raises caused both `safe_preview()` and `Runtime.execute_explicit_tool()` to raise before the tool boundary. This contradicts the stated untrusted-value boundary and turns telemetry redaction into an Agent denial-of-service/code-execution hook.

**Fix:** Traverse only exact built-in containers (`dict`, `list`, `tuple`) or first copy containers through a deliberately guarded adapter that catches ordinary exceptions and replaces the entire object with `UNSUPPORTED_OBJECT`. Do not invoke arbitrary Mapping/Sequence protocol implementations in the projector. Add hostile `Mapping.items()` and sequence-iteration tests, not only hostile `str`/`repr` tests.

### CR-04: Producer-side redaction discards truncation evidence and emits a false `truncated: false`

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/runtime/engine.py:465-468` and `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/events/normalize.py:168-174`  
**Issue:** Runtime first calls legacy `redact()`, which returns only `SafePreview.value` and discards its `truncated` flag. The normalizer then previews that already-shortened value again. A 600-character argument reaches the public envelope as 512 characters with `truncated: false`. The same double-projection pattern exists in sequential Runtime approval events and LangGraph approval requests. Consumers cannot distinguish complete evidence from clipped evidence, violating D-16.

**Fix:** Preserve projection metadata across the source boundary. For example, emit a separately allowlisted `arguments_truncated` source fact alongside the legacy redacted value, then set the public flag to `source_truncated OR normalizer_truncated`. Cover long strings, deep collections, wide collections, and unsupported nested values through actual Runtime and adapter producer paths.

### CR-05: Model-controlled tool names can crash LangGraph and suppress all Runtime telemetry

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/events/normalize.py:136-145,168-215` and `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/runtime/engine.py:1120-1145`  
**Issue:** Although `_bounded_label()` exists, most payload branches copy `tool_name` (and failure `error_type`) verbatim. Contract validation rejects values over 512 characters or containing control characters. For a LangGraph unknown-tool call with a 513-character model-supplied name, the early-rejection event raises `EventValidationError` synchronously and the node never returns its structured ToolMessage. For a registered Runtime tool with that valid v0.3 name, the tool succeeds but EventCollector rejects every lifecycle event, leaving an empty timeline.

**Fix:** Normalize every untrusted label at the projection boundary with a stable bounded/sanitized representation rather than copying then rejecting it. Alternatively, reject invalid tool names before batch lifecycle emission and turn the rejection into a valid event using a fixed safe tool label. Ensure the framework event seam never converts an ordinary model validation failure into a graph exception.

### CR-06: Approval denial leaves the run permanently marked `waiting_approval`

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/events/collector.py:35-40,262-277`  
**Issue:** The state machine returns to `running` only on approval grant, `resume_started`, or `tool_started`. The LangGraph approval path emits `approval_denied` followed by `batch_finished`, but no `resume_started` or `run_finished`. Consequently the Collector continues reporting `waiting_approval` after all decisions have been consumed and the graph node has completed. This was reproduced with an approval request, denial, and failed batch finish; the final summary remained `waiting_approval`.

**Fix:** Define and test the resolved-denial transition. For LangGraph batches, transition a waiting run back to `running` when the approval cycle is resolved (for example on `batch_finished`, or on an explicit approval-resolved/resume event). Do not infer run failure from the denial; only correct the stale waiting state.

### CR-07: Successful non-JSON tool results crash the LangGraph adapter after side effects complete

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/integrations/langgraph.py:59-62,647-659`  
**Issue:** `_result_message()` sends successful values directly to `json.dumps()`. `ToolResult.value` is unrestricted, so bytes, tuples containing unsupported objects, custom objects, cycles, and other valid Python tool returns raise `TypeError`/`ValueError`. The tool side effect has already happened and Runtime may already have emitted success, but GuardedToolNode aborts before returning messages or emitting `batch_finished`. A plain `object()` result reproduces the crash.

**Fix:** Make ToolMessage result conversion total. Preserve strings, serialize strict JSON values, and project unsupported/cyclic values through a bounded safe representation or a fixed safe placeholder. Catch serialization failure locally, return one structured ToolMessage, and always close the logical batch lifecycle in a `finally`/explicit finalization path.

### CR-08: Explicit batches accept duplicate internal call IDs and collapse distinct calls

**Classification:** BLOCKER  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/runtime/engine.py:872-916`  
**Issue:** `execute_explicit_batch()` validates correlation object types and shared batch IDs but never checks internal `call_id` uniqueness. Two inputs can supply the same authoritative call ID; both execute and every member lifecycle event is grouped under that one identity. This defeats D-06/D-09 and makes retries, approvals, and final results indistinguishable even though external `tool_call_id` duplication was intentionally separated from internal identity.

**Fix:** Before emitting `batch_started`, resolve all per-position correlations and reject duplicate non-null internal `call_id` values. Keep `tool_call_id` repeatable, but require one unique internal identity per input. Add a regression test with two distinct actions and identical supplied call IDs.

## Warnings

### WR-01: Raw-exception scanning is recursively unbounded before the bounded normalizer

**Classification:** WARNING  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/runtime/engine.py:45-59,1137-1145`  
**Issue:** `_contains_raw_exception()` recursively walks arbitrary mappings/lists/tuples with no depth or node budget and invokes custom Mapping `.values()`. A deeply nested plain dictionary raises `RecursionError` in `emit_framework_event()` before `safe_preview()` can apply its limits; a hostile Mapping can also run code or raise. This makes the supposedly narrow safety seam less robust than the contract it fronts.

**Fix:** Replace the recursive scan with a bounded iterative traversal over exact built-in containers, or remove the pre-scan and let an enhanced canonical safe projector/allowlist reject exception objects. The method should fail with a stable validation error, not recursion or attacker-defined exceptions.

### WR-02: Public `SafePreview` construction does not guarantee a safe preview

**Classification:** WARNING  
**File:** `/Users/guoshengtao/PythonProject/AgentGuard/src/agentguard/_safety.py:37-55`  
**Issue:** `SafePreview` is publicly exported, but its constructor accepts any value and immediately calls `deepcopy()`. A caller can construct `SafePreview(object(), truncated=False)`, obtain a non-JSON-compatible `to_dict()`, or trigger an attacker-defined `__deepcopy__`. The class-level API therefore does not uphold its documented strict/copy-safe contract unless callers know to use `safe_preview()` instead.

**Fix:** Make direct construction private/internal or validate/canonicalize constructor input without invoking arbitrary copy hooks. Expose a single safe factory and add a test proving direct public construction cannot create a non-JSON or side-effectful preview.

---

_Reviewed: 2026-09-06T14:13:53Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
