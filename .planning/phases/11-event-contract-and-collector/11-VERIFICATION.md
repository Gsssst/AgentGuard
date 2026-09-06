---
phase: 11-event-contract-and-collector
verified: 2026-09-06T14:22:36Z
status: gaps_found
score: 12/21 must-haves verified
overrides_applied: 0
gaps:
  - truth: "D-01/D-16/D-17/D-18: every accepted v1 preview is canonical, bounded, recursively redacted, strict-JSON-safe, and reports truncation truthfully"
    status: failed
    reason: "The public decoder accepts arbitrary preview values, long sensitive keys leak after key truncation, custom Mapping.items() can raise through Runtime, Runtime double-projection loses the truncated flag, and direct SafePreview construction bypasses safety invariants."
    artifacts:
      - path: "src/agentguard/events/contract.py"
        issue: "_preview() validates only wrapper keys/JSON compatibility; EventEnvelope.from_dict() accepted plaintext password and a 5000-character value with truncated=false."
      - path: "src/agentguard/_safety.py"
        issue: "Sensitivity is checked after key truncation, arbitrary Mapping.items() is invoked, and the public SafePreview constructor accepts unsafe values and deepcopy hooks."
      - path: "src/agentguard/runtime/engine.py"
        issue: "Producer-side redact() discards SafePreview.truncated before normalization, so clipped source evidence is published as complete."
    missing:
      - "One canonical untrusted-preview decoder/constructor that enforces the same bounds, sensitive-key masking, placeholders, JSON invariants, and truthful truncation as safe_preview()."
      - "Sensitivity matching against the original key plus a deterministic truncated-key collision policy."
      - "Traversal limited to exact safe built-in containers or guarded conversion that cannot invoke attacker-defined Mapping/sequence behavior."
      - "Propagation of source truncation metadata through Runtime and adapter approval events."
  - truth: "Runtime.emit_framework_event and adapter early-rejection paths are total, bounded, safe, and always observable"
    status: failed
    reason: "Overlong/control-bearing model labels can raise EventValidationError before a rejection event is emitted, while the raw-exception pre-scan is recursively unbounded and invokes custom Mapping.values()."
    artifacts:
      - path: "src/agentguard/events/normalize.py"
        issue: "Most tool_name/error_type branches copy labels without using the existing bounded-label projection."
      - path: "src/agentguard/runtime/engine.py"
        issue: "_contains_raw_exception() recursively traverses arbitrary Mapping values without depth/node bounds."
      - path: "src/agentguard/integrations/langgraph.py"
        issue: "An unknown 513-character tool name aborts prepare() instead of returning a structured ToolMessage and correlated failure event."
    missing:
      - "Bound/sanitize every untrusted event label before strict envelope validation."
      - "Replace the recursive raw-exception scan with bounded exact-container traversal, or move rejection into a canonical projector."
      - "Regression tests for overlong/control-bearing tool names and hostile/deep mappings at the framework seam."
  - truth: "D-19/D-20: a run summary reflects resolved LangGraph approvals and is waiting_approval only while a decision is pending"
    status: failed
    reason: "approval_denied followed by batch_finished leaves the summary permanently waiting_approval even though the approval cycle and node invocation are complete."
    artifacts:
      - path: "src/agentguard/events/collector.py"
        issue: "_RETURN_TO_RUNNING includes grant/resume/tool_started but has no resolved-denial or batch-resolution transition."
    missing:
      - "An explicit denial/resolution transition that returns the run to running without incorrectly making the run terminal."
      - "A summary-state assertion after real LangGraph denial and batch completion."
  - truth: "Every successful LangGraph tool return produces one safe final ToolMessage and closes the logical batch"
    status: failed
    reason: "A successful tool returning object() raises TypeError in json.dumps after side effects and tool_succeeded telemetry; no ToolMessage or batch_finished event is produced."
    artifacts:
      - path: "src/agentguard/integrations/langgraph.py"
        issue: "_safe_content() directly json.dumps() every non-string result and batch finalization is not protected against conversion failure."
    missing:
      - "Total bounded conversion for unsupported/cyclic/non-JSON tool results."
      - "Guaranteed batch finalization and one structured ToolMessage even when result conversion fails."
      - "Tests for bytes, custom objects, cycles, and non-finite successful results."
  - truth: "D-06/D-09: explicit-batch internal call_id values uniquely identify distinct logical calls"
    status: failed
    reason: "execute_explicit_batch() accepts duplicate supplied call_id values; two distinct calls execute and every member lifecycle is collapsed under one internal identity."
    artifacts:
      - path: "src/agentguard/runtime/engine.py"
        issue: "Correlation contexts are type-checked and batch IDs are matched, but non-null call_id uniqueness is never validated."
    missing:
      - "Resolve every per-position correlation before batch_started and reject duplicate internal call_id values while continuing to allow duplicate external tool_call_id evidence."
      - "A two-input duplicate-call-id regression test."
---

# Phase 11: Event Contract and Collector Verification Report

**Phase Goal:** Define a versioned, safe event envelope and collect Runtime/adapter events into a process-local run index.
**Verified:** 2026-09-06T14:22:36Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

The phase has substantial, wired implementation and the complete repository suite passes, but the phase goal is not achieved yet. Independent adversarial execution reproduced all eight Critical and both Warning findings in `11-REVIEW.md`. The failures cross the phase's defining safety, availability, correlation, and run-summary boundaries, so a green `212 passed` suite is not sufficient evidence for completion.

### Roadmap Success Criteria

| # | Roadmap contract | Status | Evidence |
|---|---|---|---|
| 1 | Envelopes validate identity, sequence, timestamps, type, status, and safe payload fields | ✗ FAILED | Fixed shape and ordinary validation work, but `EventEnvelope.from_dict()` accepts a plaintext password and a 5000-character preview with `truncated=false`; D-01/D-16 are violated. |
| 2 | Runtime and adapter events normalize without raw exceptions or secrets | ✗ FAILED | Long sensitive keys leak, hostile mappings abort Runtime, source truncation metadata is lost, and overlong model tool names abort the adapter or erase telemetry. |
| 3 | Collector assigns monotonic per-run sequences and exposes truthful live summaries | ✗ FAILED | Atomic sequencing passes, but approval denial followed by batch completion leaves the live summary falsely in `waiting_approval`. |
| 4 | Core import and tests remain independent of Console dependencies | ✓ VERIFIED | Isolated import tests pass; root/events imports do not load FastAPI, LangGraph, LangChain Core, or a Console package. |

### Observable Must-Haves

The 4 roadmap criteria and 22 plan truths were merged into 21 non-duplicative observable truths. D-01 through D-21 are all represented below.

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | D-01/D-02/D-03: accepted events have one strict fixed v1 contract | ✗ FAILED | Schema/version/top-level validation exists, but the event-specific preview validator accepts unsafe unbounded content. |
| 2 | D-04/D-12: undeclared source fields are rejected and only source sequence enters extensions | ✓ VERIFIED | `SOURCE_SPECS`, `_check_source_shape()`, and `_validated_extensions()` are closed; contract tests cover unknown fields. |
| 3 | D-16/D-17: argument/result previews are bounded, recursively redacted, truthful, and non-disableable | ✗ FAILED | CR-01 through CR-04 and WR-02 reproduce contract bypass, secret leakage, hostile traversal, and false truncation metadata. |
| 4 | D-18: raw exception/stack/path/reason/arbitrary-object evidence never enters or breaks v1 | ✗ FAILED | `from_dict()` can smuggle arbitrary raw content inside a preview and unsupported successful results crash downstream conversion. |
| 5 | Legacy RuntimeEvent/EventSink/redact/Runtime remain dependency-light and source-compatible | ✓ VERIFIED | Full suite passes and core import succeeds with optional Web/framework imports blocked. |
| 6 | D-06/D-09: each logical Runtime call has a distinct authoritative internal call_id | ✗ FAILED | Explicit batch accepts the same supplied `call_id` for two independent calls and groups both lifecycles under it. |
| 7 | D-07: retry, approval and checkpoint resume retain logical call identity | ✓ VERIFIED | Runtime correlation tests cover retry, approval and recovery; code closes one `EventCorrelation` over attempt/retry callbacks and derives replay IDs from run/step. |
| 8 | D-08: real run_id and separate batch_id are preserved | ✓ VERIFIED | Runtime and LangGraph paths pass a real run ID plus an independent shared batch ID; focused integration tests confirm ordinary paths. |
| 9 | D-10: legacy callers receive correlation automatically without signature breakage | ✓ VERIFIED | Optional keyword-only correlation inputs preserve existing calls; full pre-existing suite passes. |
| 10 | Framework-event seam is a total safe boundary for adapter-only facts | ✗ FAILED | CR-05 and WR-01 show ordinary model labels, deep containers, and custom mappings can raise before safe emission. |
| 11 | D-05: malformed Collector input/internal collection failure is excluded and fail-open | ✓ VERIFIED | `EventCollector.accept/emit` catch ordinary exceptions and store stable bounded diagnostics; injected-normalizer tests pass. |
| 12 | D-11/D-13/D-14: Collector atomically sequences arrival order without dedupe/reorder | ✓ VERIFIED | Barrier/thread tests produce contiguous `1..N`; duplicate and late-timestamp events remain distinct. |
| 13 | D-15: terminal runs cannot be resurrected or reused | ✓ VERIFIED | Terminal check occurs in the locked transaction and tests reject post-terminal events without consuming sequence. |
| 14 | D-19/D-20: live summary truthfully represents terminal and approval lifecycle | ✗ FAILED | Terminal-only behavior works, but resolved denial remains `waiting_approval` after `batch_finished`. |
| 15 | D-21: non-start first observation keeps null start/duration until a valid start | ✓ VERIFIED | Collector state-machine tests and code preserve `first_observed_at`, `incomplete_start`, null timing, and late-start backfill. |
| 16 | Sequence/terminal/append/summary mutation is atomic and deadlock-safe | ✓ VERIFIED | Normalization and clock run before `with self._lock`; the locked section performs only trusted envelope/state operations. Reentrant-normalizer and concurrent tests complete. |
| 17 | GuardedToolNode preserves per-input correlation across prepare/approval/resume | ✓ VERIFIED | Prepared state persists run/batch/call/external IDs and normal public StateGraph/MemorySaver resume tests retain them. |
| 18 | One logical LangGraph batch always has exactly one start/finish pair | ✗ FAILED | A non-JSON successful result emits `batch_started` but aborts before `batch_finished`. |
| 19 | Every adapter outcome is safely visible to EventCollector | ✗ FAILED | Overlong unknown tool names raise before failure emission; long registered Runtime tool names execute with zero accepted lifecycle events; non-JSON success omits final batch evidence. |
| 20 | MessagesState receives one final ordered ToolMessage per original call without replay | ✗ FAILED | Normal pause/resume behavior passes, but a valid successful tool returning `object()` yields no ToolMessage because result serialization raises. |
| 21 | Paired Chinese/English learning records document failures, design and limits | ✓ VERIFIED | Both substantive files exist with matching structure and explicit process-local/deferred-scope limits; safety claims need revision after gap closure. |

**Score:** 12/21 must-haves verified

### Decision Coverage Summary

| Decisions | Status | Notes |
|---|---|---|
| D-02, D-03, D-04, D-05 | ✓ VERIFIED | Fixed version/shape, closed fields, and Collector fail-open behavior exist. |
| D-07, D-08, D-10 | ✓ VERIFIED | Normal Runtime correlation, replay stability, and run/batch separation exist. |
| D-11 through D-15 | ✓ VERIFIED | Collector sequencing, duplicates, arrival order and terminal identity are sound. |
| D-17, D-19, D-21 | ✓ VERIFIED | No redaction off-switch, only run_finished is terminal, and incomplete-start timing is truthful. |
| D-01, D-16, D-18 | ✗ FAILED | Untrusted preview decoding, long-key masking, hostile mappings, metadata loss and unsafe direct construction violate the safety contract. |
| D-06, D-09 | ✗ FAILED | Duplicate supplied internal call IDs collapse distinct calls; some hostile adapter lifecycle paths emit no final correlated event. |
| D-20 | ✗ FAILED | A denied/resolved approval remains falsely waiting. |

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/agentguard/_safety.py` | Bounded structural redaction | ✗ DEFECTIVE | Substantive and wired, but long-key leakage, arbitrary Mapping execution, and unsafe public construction are reproducible. |
| `src/agentguard/events/contract.py` | Strict v1 envelope | ✗ DEFECTIVE | Substantive and wired; `_preview()` does not validate canonical safety/bounds. |
| `src/agentguard/events/normalize.py` | Exact mapping for all event types | ✗ DEFECTIVE | All 23 types are mapped, but untrusted labels are copied into strict fields without total projection. |
| `src/agentguard/runtime/engine.py` | Stable correlation and safe framework seam | ✗ DEFECTIVE | Ordinary correlation works; duplicate internal IDs, lost truncation metadata and unbounded exception scanning do not. |
| `src/agentguard/events/collector.py` | Atomic process-local index and summaries | ✗ DEFECTIVE | Sequencing/retention are substantive and wired, but denial resolution leaves a false summary. |
| `src/agentguard/events/__init__.py` / `src/agentguard/__init__.py` | Dependency-light public exports | ✓ VERIFIED | Exports are present, unique and importable without Web/framework dependencies. |
| `src/agentguard/integrations/langgraph.py` | Safe complete adapter lifecycle | ✗ DEFECTIVE | Normal graph flows work; hostile names and non-JSON successful results abort the node and omit evidence. |
| Phase 11 unit/integration tests | Contract, safety, collector, correlation and graph evidence | ⚠ PARTIAL | 212 tests pass but do not cover the ten reproduced review paths. |
| `11-LEARNINGS.md` / `11-LEARNINGS.en.md` | Paired learning evidence | ✓ VERIFIED | Both files are substantive and paired; final evidence should be updated after fixes. |

Automated artifact existence/substance checks reported 13/13 artifacts present. The failures above are behavioral, not missing-file/stub failures.

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| normalizer | contract | `NormalizedEvent` construction and payload registry | ✓ WIRED | `normalize_runtime_event()` creates strict facts consumed by `EventEnvelope.from_fact()`. |
| normalizer | safety projector | `safe_preview()` for arguments/results | ⚠ WIRED BUT UNSAFE | Connection exists, but producer double-projection and unsafe mapping/key handling violate the intended boundary. |
| permission API | shared safety | `redact()` compatibility wrappers | ✓ WIRED | Existing permission/digest tests pass. |
| Runtime explicit execution | ToolExecutor | one correlation closed over `on_event` | ✓ WIRED | Attempt/retry callbacks use the same correlation on normal paths. |
| Runtime resume | Runtime run | deterministic UUID5 run/step coordinate | ✓ WIRED | Recovery tests confirm stable ordinary call identity. |
| EventCollector accept | normalizer/envelope/summary | normalize before lock, commit under lock | ✓ WIRED | Atomic sequence and state mutation are connected. |
| GuardedToolNode prepare/approval | Runtime framework/batch APIs | persisted per-input contexts | ⚠ WIRED BUT INCOMPLETE | Normal public graph path works; hostile name/result branches abort before complete telemetry. |
| Runtime event_sink | EventCollector | injected `EventSink.emit()` | ✓ WIRED | Tests attach Collector directly; no Console dependency is introduced. |
| LangGraph integration tests | MessagesState/MemorySaver/Command | public framework APIs | ✓ WIRED | Real pause/resume test passes with pinned optional dependencies. |

The generic key-link query could not resolve symbolic `Runtime.*` and `EventCollector.*` names as filesystem paths, so those links were traced manually in source and executed tests.

## Data-Flow Trace (Level 4)

| Artifact | Data | Source | Produces real data | Status |
|---|---|---|---|---|
| `EventCollector` | Envelope timeline | RuntimeEvent → normalizer → locked commit | Yes for accepted ordinary facts | ⚠ FLOWING WITH SAFETY GAPS |
| `RunSummary` | status/count/timing | accepted envelopes → `_advance_summary()` | Yes, except denial resolution | ✗ FALSE STATE PATH |
| `GuardedToolNode` | ToolMessage + lifecycle timeline | AIMessage → Runtime explicit/framework APIs → Collector | Yes for tested JSON-returning paths | ✗ DISCONNECTED ON HOSTILE NAME/NON-JSON RESULT |

No UI-rendering artifact belongs to Phase 11; React data-flow verification is correctly deferred to Phase 14.

## Independent Review-Finding Reproduction

| Finding | Independent probe result | Status |
|---|---|---|
| CR-01 | `EventEnvelope.from_dict()` returned `PLAINTEXT`, retained a 5000-character value, and kept `truncated=False`. | ✓ REPRODUCED |
| CR-02 | `safe_preview({"x"*512+"password": "LEAK"})` serialized `LEAK`; output key length was 512. | ✓ REPRODUCED |
| CR-03 | A custom nested Mapping caused `RuntimeError: EVIL_ITEMS_CALLED` from both `safe_preview()` and `Runtime.execute_explicit_tool()`. | ✓ REPRODUCED |
| CR-04 | A 600-character Runtime argument reached v1 at length 512 with `truncated=False`. | ✓ REPRODUCED |
| CR-05 | Unknown 513-character adapter name raised `EventValidationError`; a registered 513-character Runtime tool succeeded but Collector retained 0 events and recorded 4 `invalid_value` rejections. | ✓ REPRODUCED |
| CR-06 | approval request → denial → failed batch finish produced final summary `waiting_approval`. | ✓ REPRODUCED |
| CR-07 | Successful `object()` tool result raised `TypeError`; timeline ended at `tool_succeeded` without `batch_finished`. | ✓ REPRODUCED |
| CR-08 | Two distinct explicit-batch calls with supplied `call_id="DUPLICATE"` both succeeded; unique internal IDs were exactly `["DUPLICATE"]`. | ✓ REPRODUCED |
| WR-01 | A 1500-level dict raised `RecursionError`; hostile Mapping raised `RuntimeError: EVIL_VALUES_CALLED` in `emit_framework_event()`. | ✓ REPRODUCED |
| WR-02 | `SafePreview(object(), truncated=False)` produced a non-JSON value; hostile `__deepcopy__` raised `EVIL_DEEPCOPY_CALLED`. | ✓ REPRODUCED |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full repository regression suite | `PYTHONPATH=src pytest -q` | `212 passed in 1.39s` | ✓ PASS |
| Atomic sequencing and reentrant-normalizer deadlock guard | Focused Collector tests | Passed | ✓ PASS |
| Real MessagesState/MemorySaver approval resume | Focused LangGraph test | Passed with one third-party deprecation warning | ✓ PASS |
| Core import | `PYTHONPATH=src python -c "import agentguard; ..."` | `core import: PASS` | ✓ PASS |
| Adversarial Phase 11 safety/correlation/status matrix | Independent in-memory Python probe | All 8 Critical and 2 Warning defects reproduced | ✗ FAIL |
| Patch whitespace | `git diff --check` before report creation | Passed | ✓ PASS |

The passing suite is a regression signal, not proof of the hostile-input contract: existing tests cover a hostile generic object's string conversion, but not custom Mapping methods; JSON object results, but not arbitrary successful values; approval grant transitions, but not denial completion; and generated distinct IDs, but not duplicate supplied internal IDs.

## Probe Execution

No phase-declared or conventional `scripts/**/tests/probe-*.sh` files exist. The required review claims were instead executed independently as bounded, in-memory behavioral probes; no service was started and no external state was mutated.

## Requirements Coverage

| Requirement | Source plans | Status | Evidence |
|---|---|---|---|
| OBS-03 | 11-01, 11-02, 11-03, 11-04 | ✗ BLOCKED | Fixed v1 shape and monotonic sequence exist, but accepted/collected payload safety and truthful truncation do not hold. |
| OBS-04 | 11-01, 11-02, 11-03, 11-04 | ✗ BLOCKED | Ordinary lifecycle types are modeled, but secrets can leak and several adapter/runtime outcomes disappear or crash. |
| COMPAT-01 | 11-01, 11-03, 11-04 | ✓ SATISFIED | Core import and all tests run without Console FastAPI/frontend dependencies; optional LangGraph remains outside core imports. |

No additional Phase 11 requirement is orphaned. OBS-01/02, HISTORY, STREAM, INGEST, DEMO and frontend compatibility requirements remain mapped to Phases 12-14.

## Anti-Patterns Found

| File | Line(s) | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/agentguard/events/contract.py` | 170-175 | Wrapper-shape validation mistaken for canonical safe-preview validation | 🛑 Blocker | Public decoder bypasses the safety boundary. |
| `src/agentguard/_safety.py` | 48-58, 98-100, 126-140 | Public unsafe constructor and arbitrary Mapping protocol execution | 🛑 Blocker | Data leak, attacker hook, and Runtime denial of service. |
| `src/agentguard/runtime/engine.py` | 461-468, 55-68, 1137-1145 | Double projection plus recursively unbounded pre-scan | 🛑 Blocker | False telemetry and unbounded/hostile traversal. |
| `src/agentguard/integrations/langgraph.py` | 59-62, 647-659 | Unrestricted JSON serialization after successful side effect | 🛑 Blocker | Graph abort and missing batch/result evidence. |
| `src/agentguard/events/collector.py` | 35-40, 262-277 | Incomplete approval-resolution state transition | 🛑 Blocker | Live run summary is observably false. |

No unreferenced `TBD`, `FIXME`, or `XXX` debt markers were found in the Phase 11 changed files. The two textual `placeholder` matches describe fixed safe placeholders and MessagesState semantics, not stubs.

## Deferred-Scope Check

No gap above is legitimately deferred to a later phase. Phase 12 explicitly depends on safe validated envelopes for JSONL/REST, Phase 13 depends on their ordering for SSE/ingestion, and Phase 14 depends on truthful summaries/events for display. Persisting or streaming the present unsafe/false data would amplify these defects.

Conversely, JSONL persistence, REST endpoints, SSE, external ingestion, React UI, web approvals, distributed locking and HA are not required to satisfy Phase 11 and were not treated as gaps.

## Human Verification Required

None. All goal-relevant behavior is library/runtime behavior and was verified or disproved programmatically.

## Gaps Summary

Five root concerns block the phase goal: the canonical preview boundary is bypassable and non-total; framework labels/raw-exception scanning can abort observability; denied approvals leave false live state; successful non-JSON tool results abort LangGraph after side effects; and explicit batches allow duplicate authoritative call IDs. These account for all eight independently reproduced Critical findings and both Warnings.

Use `$gsd-plan-phase 11 --gaps` to create focused closure plans from the structured frontmatter above. Phase 12 should not begin until the five concerns are fixed and re-verified.

---

_Verified: 2026-09-06T14:22:36Z_
_Verifier: the agent (gsd-verifier)_
