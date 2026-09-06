# Phase 11: Event Contract and Collector - Pattern Map

**Mapped:** 2026-09-06
**Files analyzed:** 22 source/test files plus Phase 11 planning context
**Expected new/modified files:** 17 (2 checkpoint files conditional)
**Strong analog groups:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/agentguard/_safety.py` (new) | utility | transform | `src/agentguard/runtime/permission.py` | role + exact safety concern |
| `src/agentguard/events/contract.py` (new) | model | transform/validation | `src/agentguard/events/model.py`; `src/agentguard/checkpoint/model.py` | exact model style |
| `src/agentguard/events/normalize.py` (new) | service | transform | `src/agentguard/checkpoint/codec.py`; `src/agentguard/reporting/report.py` | role-match |
| `src/agentguard/events/collector.py` (new) | service/store | event-driven | `src/agentguard/events/sinks.py`; `src/agentguard/runtime/resources.py` | partial; no exact collector exists |
| `src/agentguard/events/__init__.py` | provider/export | transform | current `src/agentguard/events/__init__.py` | exact |
| `src/agentguard/__init__.py` | provider/export | transform | current `src/agentguard/__init__.py` | exact |
| `src/agentguard/runtime/permission.py` | utility | transform | current `redact()` and `canonicalize()` | exact migration seam |
| `src/agentguard/runtime/engine.py` | service/controller | event-driven | current `_emit*`, run/resume, explicit/batch execution paths | exact |
| `src/agentguard/checkpoint/model.py` (conditional) | model | file-I/O state | current `Checkpoint` | exact |
| `src/agentguard/checkpoint/codec.py` (conditional) | utility/codec | transform/file-I/O | current explicit encode/decode functions | exact |
| `src/agentguard/integrations/approval.py` | model/service | event-driven | current `ApprovalItem`, `ApprovalBatch`, `build_approval_batch()` | exact |
| `src/agentguard/integrations/langgraph.py` | adapter/middleware | event-driven | current `GuardedToolNode.prepare()` / `approval()` | exact |
| `tests/unit/test_event_contract.py` (new) | test | transform/validation | `tests/unit/test_domain_models.py`; `tests/unit/test_checkpoint.py` | exact test style |
| `tests/unit/test_event_safety.py` (new) | test | transform | `tests/unit/test_redaction_and_digest.py` | exact concern, broader cases needed |
| `tests/unit/test_event_collector.py` (new) | test | event-driven/concurrent | `tests/unit/test_event_sinks.py`; `tests/unit/test_resource_locks.py` | role-match |
| `tests/integration/test_event_correlation.py` (new) | test | event-driven | `tests/integration/test_recovery_scenarios.py`; `tests/integration/test_batch_concurrency.py` | exact lifecycle analog |
| `tests/integration/test_langgraph_observability.py` (new) | test | event-driven | `tests/integration/test_langgraph_approval.py`; `tests/integration/test_langgraph_optional.py` | exact adapter analog |

The checkpoint files are conditional. If sequential Runtime `call_id` is deterministically derived only from the non-secret logical coordinate `run_id + step`, no new persisted field is required. If the implementation chooses random IDs, the pending action's ID must be added to both the model and codec in the same task; changing only one side would break recovery.

`src/agentguard/events/model.py`, `src/agentguard/events/sinks.py`, `src/agentguard/runtime/tool.py`, and `src/agentguard/reporting/report.py` are primarily compatibility/reference files. Prefer leaving their public behavior intact unless a narrowly scoped import/export change is required.

## Current Event and Correlation Flow

```text
Runtime.run / execute_explicit_tool / execute_*_batch
        |
        +-- ToolExecutor on_event(EventType, free-form data)
        |       `-- attempts + retry facts, no run/call/batch identity
        |
        `-- Runtime._emit / _emit_external / _emit_batch_event
                `-- RuntimeEvent(event_type, run_id, step, data, timestamp)
                        `-- EventSink.emit(event)
                              +-- InMemoryEventSink.events
                              +-- legacy JsonlEventSink
                              `-- ReliabilityReport consumer

GuardedToolNode.prepare/approval
        +-- obtains real run_id from RunnableConfig
        +-- preserves external tool_call_id only in local tuples/state
        +-- builds approval batch_id only for interrupt payload
        `-- calls Runtime.execute_explicit_batch(run_id=...)
                `-- external tool_call_id and approval batch_id are lost before emit
```

### Identity Gap Map

| Identity | Current source and path | Current gap | Phase 11 seam |
|---|---|---|---|
| `run_id` | Sequential runs use `RunState.run_id` (`engine.py:78-81`); adapter reads config or generates UUID (`langgraph.py:422-432`). | `execute_batch()` sends `batch_id` into `RuntimeEvent.run_id` (`engine.py:527-551, 793-803`). | Add a real run ID to every batch path and pass batch identity separately. |
| `tool_call_id` | Read/mapped in adapter (`langgraph.py:172-215`) and retained in `ToolMessage`/prepared state (`langgraph.py:248-295`). | It never enters Runtime emitters, retries, or final tool events; invalid placeholders are not globally unique. | Put it in one immutable correlation context; preserve it as nullable source evidence only. |
| `batch_id` | Approval helper derives one from `run_id + external IDs + digest + index` (`approval.py:137-184`). | Direct Runtime batches have no separate event field; mixed approval/direct subsets can emit misleading separate boundaries. | Create once at the logical batch boundary, persist in prepared state, and propagate to every member/boundary event. |
| `call_id` | No internal logical-call field exists. Locals named `call_id` in `langgraph.py` are actually external `tool_call_id` values (`langgraph.py:325-372`). | Retries, approval resume, and crash replay cannot be grouped without inference. | Generate at the producer boundary; close over it in `ToolExecutor` callbacks and persist/derive it across resume. |
| source `sequence` | Runtime increments `_event_sequence` and inserts `data.sequence` (`engine.py:777-812`); checkpoint restores `event_position` (`engine.py:277-280`). | It is Runtime-instance scoped, can resume/reset, and is not safe as a cross-producer cursor. | Normalizer may copy it only to `extensions.source_sequence`; Collector assigns authoritative top-level sequence. |

## Pattern Assignments

### `src/agentguard/events/contract.py` (model, strict validation)

**Analogs:** `src/agentguard/events/model.py`, `src/agentguard/checkpoint/model.py`

**Imports and closed vocabulary pattern** (`events/model.py:3-9`):

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

class EventType(StrEnum):
    ...
```

Reuse `StrEnum` for `EventStatus`, `RunSummaryStatus`, diagnostic/result codes, and frozen dataclasses for public snapshots. Keep `EventType` as the existing canonical 23-value vocabulary rather than creating a second list.

**Fail-fast model validation pattern** (`events/model.py:39-58`):

```python
@dataclass(frozen=True)
class RuntimeEvent:
    ...
    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EventType):
            raise TypeError("event_type must be an EventType")
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if self.step < 0:
            raise ValueError("step cannot be negative")
        object.__setattr__(self, "data", dict(self.data))
```

Copy the explicit validation and defensive-copy style, but tighten it: reject `bool` where integers are expected, validate nullable identity fields, normalize aware timestamps to UTC, require `sequence >= 1`, and validate the per-event payload spec. Use `kw_only=True` for the larger fixed envelope.

**Cross-field invariant pattern** (`checkpoint/model.py:58-104`):

```python
if not isinstance(self.max_steps, int) or isinstance(self.max_steps, bool) or self.max_steps <= 0:
    raise CheckpointValidationError("max_steps must be a positive integer")
...
if self.state.status.value == "waiting_approval":
    if not isinstance(self.pending_action, CallTool) or self.action_digest is None:
        raise CheckpointValidationError(...)
```

Use the same pattern for envelope invariants: tool lifecycle events require `call_id`; run-level events require `call_id is None`; batch events require `batch_id`; `run_finished` accepts only terminal payload statuses; `batch_finished.failed` must be within `0..size`.

Do **not** change legacy `RuntimeEvent.to_dict()` (`events/model.py:60-69`) into the v1 envelope. `ReliabilityReport` directly consumes `RuntimeEvent` and its free-form `data` (`report.py:68-115`), so replacement would break v0.3 compatibility.

---

### `src/agentguard/events/normalize.py` (service, source fact -> safe fact)

**Analogs:** `src/agentguard/checkpoint/codec.py`, `src/agentguard/reporting/report.py`

**Explicit projection pattern** (`checkpoint/codec.py:187-206`):

```python
return {
    "schema_version": checkpoint.schema_version,
    "lifecycle": checkpoint.lifecycle.value,
    "run_id": checkpoint.run_id,
    "state": _encode_state(checkpoint.state),
    "event_position": checkpoint.event_position,
    ...
}
```

Copy the explicit field-by-field projection style. Define one declarative payload specification for every `EventType`; consume only named legacy keys and reject unknown ones. Never use `payload.update(event.data)` or `extensions.update(unconsumed_data)`.

**Strict decode/error wrapping pattern** (`checkpoint/codec.py:238-283`):

```python
if not isinstance(raw, dict):
    raise CheckpointValidationError("checkpoint must be an object")
for key in (...):
    _require(raw, key, "checkpoint")
...
except (TypeError, ValueError, CheckpointValidationError) as exc:
    ...
    raise CheckpointValidationError(f"invalid checkpoint: {exc}") from exc
```

Use a dedicated `EventValidationError` plus stable diagnostic codes. The private exception chain may preserve cause for tests, but Collector diagnostics must not include `str(exc)` or raw candidate data.

**Compatibility consumer evidence** (`report.py:71-93`):

```python
event_list = tuple(events)
event_dicts = tuple(event.to_dict() for event in event_list)
finished = [event for event in event_list if event.event_type is EventType.RUN_FINISHED]
...
retry_count = sum(event.event_type is EventType.RETRY_SCHEDULED for event in event_list)
```

Normalizer should accept the legacy source object without modifying what existing report/CLI consumers see. It should map raw `value` to a bounded `result` preview, raw `error_message` to a fixed safe summary, and source `data.sequence` only to the named `extensions.source_sequence`.

---

### `src/agentguard/_safety.py` and `runtime/permission.py` (bounded safe projection)

**Analog:** `src/agentguard/runtime/permission.py`

**Existing redaction semantics** (`permission.py:234-262`):

```python
_DEFAULT_SENSITIVE_MARKERS = (
    "password", "token", "secret", "api_key",
    "access_key", "private_key", "authorization",
)

if isinstance(value, dict):
    ...
    if any(marker in key_text.lower() for marker in markers):
        result[key] = "[REDACTED]"
    else:
        result[key] = redact(item, sensitive_fields=sensitive_fields)
```

Preserve the marker vocabulary and non-mutating recursive behavior. Move the implementation downward into `_safety.py` so the events package does not import the runtime package, then keep `runtime.permission.redact` / `redact_arguments` as compatibility wrappers.

**Do not copy the current limitations:** `redact()` has no depth, width, node, string, cycle, or JSON-finiteness bounds. It returns arbitrary objects unchanged. The adapter's `_jsonable()` is also unsafe as a v1 pattern because it calls `str(value)` for unsupported objects (`approval.py:23-32`). Phase 11 projection must traverse only JSON primitives/mappings/lists/tuples, redact keys before descending, detect cycles, normalize/reject non-finite floats, and return explicit `{value, truncated}` previews without invoking arbitrary `repr()`/`str()`.

**Existing test seed** (`test_redaction_and_digest.py:4-14`):

```python
projected = redact(first.arguments)
assert projected["password"] == "[REDACTED]"
assert projected["nested"][0]["TOKEN"] == "[REDACTED]"
assert first.arguments["password"] == "top-secret"
```

Extend this pattern with table-driven cases for deep/wide/cyclic structures, long strings, NaN/Infinity, bytes, unsupported objects, mutation after collection, and exception text containing tokens/paths/newlines.

---

### `src/agentguard/events/collector.py` (thread-safe, bounded process-local index)

**Analogs:** `events/sinks.py` for the interface; `runtime/resources.py` for disciplined critical sections. There is no exact thread-safe collector analog.

**Sink compatibility seam** (`events/sinks.py:10-24`):

```python
class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None:
        """Persist or retain one event."""

class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []
    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)
```

Implement `EventCollector.emit(RuntimeEvent) -> None` so it can be injected into `Runtime.event_sink` unchanged. Add a separate typed `accept()` result for tests/future ingestion. Return immutable snapshots (`tuple`, frozen `RunSummary`) rather than exposing mutable internal containers.

**Critical-section discipline analog** (`resources.py:85-104`):

```python
acquired = []
try:
    for resource, mode in normalized.items():
        await self._acquire_one(resource, mode, deadline)
        acquired.append((resource, mode))
    yield
finally:
    for resource, mode in reversed(acquired):
        await self._release_one(resource, mode)
```

Reuse the principle that state transitions are complete and cleanup is explicit, but do **not** copy `asyncio.Condition`: `EventSink.emit()` is synchronous and may be called from OS threads. Use `threading.Lock`, precompute clock/normalization outside it, then perform terminal check + next sequence + envelope construction + append + summary replacement atomically under one lock. Never call a user clock, serializer, callback, downstream sink, or diagnostic formatter while holding it.

**Run summary state pattern:** follow the cross-field validation style above and encode transitions in a table/function. `tool_failed`, timeout, permission denial, approval denial, and `batch_finished(failed>0)` do not make the run terminal; only `run_finished` does. The first non-start event creates `running/incomplete_start=true`; a later start can backfill `started_at` without changing earlier sequence values.

**Bounded retention:** use `deque(maxlen=...)` for per-run events and diagnostics, maintain `event_count`, `retained_event_count`, `first_retained_sequence`, and `last_sequence` separately, and bound the run index. Evict oldest terminal runs first; reject a new run rather than evicting active/waiting runs when capacity is full.

**Do not copy:** `InMemoryEventSink.events` is an unbounded public mutable list; `JsonlEventSink` writes legacy data directly (`sinks.py:27-38`) and belongs to the old compatibility path, not Phase 11 history.

---

### `src/agentguard/runtime/engine.py` and `runtime/tool.py` (producer correlation)

**Analog:** current Runtime emitter/callback chain.

**Reusable callback seam** (`tool.py:175-188, 226-240`):

```python
for attempt in range(1, self._retry_policy.max_attempts + 1):
    if on_event is not None:
        on_event(EventType.TOOL_ATTEMPT_STARTED, {"tool_name": ..., "attempt": attempt, ...})
...
if on_event is not None:
    on_event(EventType.RETRY_SCHEDULED, {"completed_attempt": attempt, ...})
```

`ToolExecutor` should remain unaware of run identity. In Runtime, create one immutable correlation context before execution and close over it in the callback, mirroring the current lambda (`engine.py:183-187`, `484-489`) while adding the context:

```python
on_event=lambda event_type, data: self._emit_external(
    event_type, run_id, step, correlation=correlation, **data
)
```

This naturally gives attempts/retries the same `call_id` without widening every ToolExecutor payload.

**Current emitter seam and bug** (`engine.py:777-812`):

```python
def _emit(self, event_type, state, **data):
    self._event_sequence += 1
    data.setdefault("sequence", self._event_sequence)
    self.event_sink.emit(RuntimeEvent(..., run_id=state.run_id, ...))

def _emit_batch_event(self, event_type, batch_id, **data):
    ...
    RuntimeEvent(..., run_id=batch_id, step=0, data=data)
```

Keep a single construction path but add explicit correlation fields to source `data` (or a small internal correlation DTO consumed there). Batch emit must receive both `run_id` and `batch_id`; never write `batch_id` into `RuntimeEvent.run_id`. Keep legacy source sequence for reports/checkpoints but treat it only as source metadata.

**Raw-data leaks to remove from v1 projection, not necessarily from legacy `ToolResult`:**

- tool success includes raw `value` (`engine.py:207-214`, `508-509`);
- tool failure and lock timeout include raw `error_message` (`engine.py:188-203`, `231-244`, `490-504`, `515-523`);
- resume/checkpoint events include local paths (`engine.py:313-319`, `839-845`);
- loop event includes action signature based on arguments (`engine.py:166-175`).

The strict normalizer is the final disclosure boundary. Source emitters should still stop adding obviously unnecessary raw fields where compatibility permits, but do not remove fields that current reports/tests need without evidence.

---

### `checkpoint/model.py` and `checkpoint/codec.py` (correlation across recovery, conditional)

**Analogs:** existing versioned model + exact codec.

**Current recovery fields** (`checkpoint/model.py:40-56`):

```python
@dataclass
class Checkpoint:
    run_id: str
    state: RunState
    event_position: int = 0
    resume_attempt: int = 0
    pending_action: Action | None = None
    ...
    duplicate_possible: bool = False
    schema_version: int = 1
```

If a persisted `pending_call_id` is needed, validate it beside `pending_action`: it must be non-empty when present and must require a pending `CallTool`. Keep decode backward-compatible by reading new optional keys with `.get()` rather than adding them to the required-key tuple.

**Paired codec pattern** (`checkpoint/codec.py:192-206, 238-277`):

```python
"pending_action": _encode_action(checkpoint.pending_action),
"pending_capabilities": sorted(checkpoint.pending_capabilities),
...
pending_action=_decode_action(raw["pending_action"], field="checkpoint.pending_action"),
pending_capabilities=raw.get("pending_capabilities", []),
```

Any model addition must be encoded, decoded, validated, and covered by round-trip/old-fixture tests together. Do not bump the checkpoint version for an optional backward-compatible field. If deterministic `uuid5(run_id + step)` is used, prefer no checkpoint schema change and add recovery tests proving identity stability.

---

### `integrations/approval.py` and `integrations/langgraph.py` (adapter correlation and missing event paths)

**Analogs:** typed approval projection and prepared state.

**Typed versioned projection pattern** (`approval.py:35-105`):

```python
@dataclass(frozen=True)
class ApprovalItem:
    tool_call_id: str
    ...
    input_index: int

@dataclass(frozen=True)
class ApprovalBatch:
    batch_id: str
    items: tuple[ApprovalItem, ...]
    payload_version: str = PAYLOAD_VERSION
```

Use the same typed, frozen, versioned structure for correlation, but do not reinterpret `tool_call_id` as the new internal ID. Add/persist a distinct `call_id` in the private prepared context (and only in the approval public projection if deliberately versioned compatibly).

**Prepared-state persistence seam** (`langgraph.py:259-295`):

```python
approval_batch = build_approval_batch(..., run_id=run_id, batch_id=state.get("_agentguard_batch_id"))
context = {
    "run_id": run_id,
    "batch": approval_batch.to_dict(),
    "pending": [{"input_index": index, "tool_call_id": call_id, ...}],
    ...
}
return {"_agentguard_prepared": context}
```

Generate the logical `batch_id` before splitting immediate/executable/pending calls, create one internal `call_id` per original input, and retain both IDs in the prepared context. Resume must reuse them when calling Runtime. The same batch identity must cover the original AIMessage rather than each executed subset.

**Run identity pattern** (`langgraph.py:422-432`):

```python
configurable = config.get("configurable")
...
return f"langgraph-{uuid.uuid4().hex}"
```

Reuse caller-provided run IDs and opaque random fallback. Never derive call/batch IDs from arguments, exception messages, actor/reason text, or other sensitive fields.

**Missing source-event branches** (`langgraph.py:181-239, 325-351`): invalid calls, duplicate IDs, unknown tools, missing guards, policy denials, pending approvals, missing decisions, digest mismatch, and missing tools after resume currently create only `ToolResult`/`ToolMessage` values. Add a Runtime-owned framework-event emission seam so each branch emits a safe correlated event without invoking a Tool.

**Do not copy these old assumptions:**

- `_mapped_tool_call_id()` creates `agentguard-invalid-call-{index}` (`langgraph.py:389-395`); this is output compatibility, not an internal primary key.
- `ApprovalBatch` requires unique external IDs (`approval.py:86-94`); the v1 event contract itself must not rely on that property.
- `_error_content()` uses fixed messages and is a good safe-summary analog (`langgraph.py:63-85`), but success `_safe_content()` serializes raw values (`langgraph.py:57-60, 409-420`) and is not a telemetry projection.
- `_jsonable()` falls back to `str(value)` (`approval.py:23-32`); do not use it for untrusted telemetry.

## Test Pattern Assignments

### Contract and validation tests

Use table-driven invalid factories like `tests/unit/test_domain_models.py:25-35`:

```python
@pytest.mark.parametrize("factory", [...])
def test_actions_reject_invalid_values(factory) -> None:
    with pytest.raises((ValueError, TypeError)):
        factory()
```

Create one valid fixture per `EventType`, then vary schema version, missing/extra payload keys, empty/overlong IDs, bool-as-int, negative sequence, naive/non-UTC timestamp, invalid status, and correlation nullability. Assert stable validation/diagnostic categories, not raw exception strings.

### Copy/immutability and sink compatibility tests

Reuse `tests/unit/test_event_sinks.py:6-14, 38-43`:

```python
sink.emit(first)
sink.emit(second)
assert sink.events == [first, second]
...
data["tool_name"] = "mutated"
assert event.data["tool_name"] == "echo"
```

For v1, mutate nested caller containers after acceptance and assert collected snapshots do not change. Also inject `EventCollector` as `Runtime.event_sink` and prove malformed events/normalizer failures cannot interrupt a surrounding run.

### Collector concurrency tests

The closest concurrency style is `tests/unit/test_resource_locks.py:36-52, 85-102`: coordinate work with Events and assert invariants after all tasks complete. For Collector use `ThreadPoolExecutor` plus a barrier (not `asyncio.Event`) because the contract is cross-thread. Submit interleaved events for two run IDs and assert each receives exactly `1..N`, no duplicates, and summary counts agree. Do not assert a particular thread acquisition order.

### Runtime recovery correlation tests

Reuse deliberate crash/resume setup from `tests/integration/test_recovery_scenarios.py:28-83`:

```python
with pytest.raises(SimulatedCrash):
    await runtime.run(...)
...
result = await resumed.resume(path, ResultRouter())
assert result.run_id == "run-recovery"
assert any(event.event_type is EventType.RESUME_STARTED for event in sink.events)
```

Add assertions that the pre-crash/replayed logical call keeps one `call_id`, while `attempt`, `resume_attempt`, and `duplicate_possible` retain execution evidence. Also test approval pause/resume with a stable ID.

### Batch correlation tests

Reuse `tests/integration/test_batch_concurrency.py:9-35, 66-81`: coordinate overlap, preserve result input order, and isolate failures. Extend assertions over collected events: one real run ID, one shared batch ID, distinct internal call IDs, stable call ID over retry, and no dependence on duplicate/invalid external IDs.

### Real LangGraph tests

Reuse optional import guards and real `StateGraph`/checkpointer setup from `tests/integration/test_langgraph_approval.py:8-55`, then mirror the interrupt/resume assertion style at lines 68-110. Existing tests already prove external IDs and MessagesState order (`test_langgraph_approval.py:188-241`; `test_langgraph_optional.py:66-94`). New observability tests must additionally attach an `EventCollector` and assert:

- direct, pending, denied, invalid, unknown, digest-mismatch, retry, timeout, and final result paths all emit safe events;
- `tool_call_id` remains the original source ID where valid;
- internal `call_id` is stable and distinct from the external ID;
- direct work is not replayed after approval resume;
- `import agentguard` succeeds without importing LangGraph/FastAPI/frontend dependencies.

## Shared Patterns

### Validation and immutable public snapshots

**Sources:** `events/model.py:39-58`, `checkpoint/model.py:58-104`, `runtime/resources.py:27-46`

Apply explicit runtime checks, reject `bool` as integer, normalize before storage, defensively copy containers, and return immutable structures (`frozenset`, tuple, `MappingProxyType`, frozen dataclass) at public boundaries.

### Failure isolation and safe summaries

**Sources:** `runtime/tool.py:197-216`, `integrations/langgraph.py:63-85`

The Tool boundary converts exceptions into typed `ToolResult`; the adapter maps failure categories to fixed human-safe text. Collector should catch `Exception` (not `BaseException`), record only type/category/code, and return without breaking the observed Agent. Never serialize raw `error_message`, exception stack, or candidate event into normal events or diagnostics.

### Optional dependency boundary

**Sources:** `integrations/langgraph.py:13-20`, `events/__init__.py:1-12`, root `__init__.py:1-42`

New contract/collector/safety modules must use only the standard library and core AgentGuard types. Events may be exported from `agentguard.events` and root `agentguard`, but those imports must not reach `agentguard.integrations.langgraph`, FastAPI, or frontend modules. Optional integration tests should keep `pytest.importorskip()` (`test_langgraph_optional.py:1-7`).

### Compatibility boundary

**Sources:** `events/sinks.py:27-38`, `reporting/report.py:68-115`

Legacy `RuntimeEvent`, `JsonlEventSink`, and `ReliabilityReport` remain valid in Phase 11. Add the v1 boundary beside them. Phase 12, not Phase 11, will introduce validated v1 JSONL history.

## Patterns Not to Copy

| Existing pattern | Location | Why it is unsafe/wrong for Phase 11 |
|---|---|---|
| Free-form `RuntimeEvent.data` becomes public output | `events/model.py:40-69` | Violates per-event allowlists and stable v1 semantics. Keep it only as legacy source input. |
| Unbounded public list | `events/sinks.py:17-24` | Collector needs bounded retention and immutable snapshots. |
| Immediate legacy JSONL write | `events/sinks.py:27-38` | Phase 12 owns v1 persistence; writing before validation leaks unsafe data. |
| Recursive redaction without bounds/cycle handling | `runtime/permission.py:245-262` | Vulnerable to deep/wide/cyclic payload exhaustion and unsupported objects. |
| Arbitrary `str(value)` fallback | `integrations/approval.py:23-32` | Can leak secrets or invoke user-defined code. |
| Raw exception messages/paths/signatures in event data | `engine.py:188-203, 231-244, 313-319, 839-845` | Must never cross the v1 boundary. |
| Runtime `_event_sequence` as public ordering | `engine.py:777-812` | Not authoritative across Runtime, adapter, resume, or concurrent sources. |
| `batch_id` used as `run_id` | `engine.py:527-551, 793-803` | Splits/corrupts logical run summaries. |
| External `tool_call_id` as logical primary key | `approval.py:86-94`; `langgraph.py:325-372` | External IDs may be null/invalid/duplicate and are source evidence only. |
| Inferring correlation from arrival order | no current helper | Concurrency/retry/resume makes adjacency ambiguous; producer must supply IDs. |
| Callbacks or recursive diagnostics under Collector lock | no current collector | Risks deadlock/re-entry; only atomic state mutation belongs under lock. |

## No Exact Analog Found

| File/Concern | Role | Data Flow | Reason / Planner Direction |
|---|---|---|---|
| `events/collector.py` atomic cross-thread run index | service/store | event-driven/concurrent | Existing sinks are neither bounded nor thread-safe; resource locks are asyncio-only. Follow research's `threading.Lock` transaction and bounded deque design. |
| Strict per-`EventType` payload registry | model/validator | transform | Current `RuntimeEvent.data` is intentionally free-form. Use the research payload matrix; do not extrapolate legacy keys automatically. |
| Internal `call_id` lifecycle | model/correlation | event-driven | No internal field exists. Generate at Runtime/adapter source, propagate through callbacks/prepared state, and prove resume stability in tests. |
| Run summary state machine | model/store | event-driven | `RunState` tracks execution, not observation. Implement a separate frozen summary and explicit transition table. |

## Planner-Facing Implementation Order

1. Build shared bounded safety projection and strict contract/normalizer tests first; preserve legacy types.
2. Repair Runtime/adapter producers so real `run_id`, `batch_id`, `call_id`, and nullable `tool_call_id` exist before strict end-to-end collection.
3. Implement the Collector transaction, bounded summaries/diagnostics, and concurrent tests once producers satisfy correlation requirements.
4. Finish with Runtime, checkpoint/approval resume, batch, and real LangGraph integration evidence plus dependency-isolation verification.

This order avoids a misleading state where synthetic unit envelopes pass while real Runtime/adapter events are rejected by the strict collector.

## Metadata

**Analog search scope:** `src/agentguard/{events,runtime,checkpoint,integrations,reporting}`, `tests/{unit,integration}`

**Primary source analogs:**

- `src/agentguard/events/model.py`
- `src/agentguard/events/sinks.py`
- `src/agentguard/runtime/permission.py`
- `src/agentguard/runtime/engine.py`
- `src/agentguard/runtime/tool.py`
- `src/agentguard/checkpoint/model.py`
- `src/agentguard/checkpoint/codec.py`
- `src/agentguard/integrations/approval.py`
- `src/agentguard/integrations/langgraph.py`
- `src/agentguard/runtime/resources.py`
- `src/agentguard/reporting/report.py`

**Pattern extraction date:** 2026-09-06

