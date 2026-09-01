# Phase 5: Permission Control and Approval Boundaries - Pattern Map

**Mapped:** 2026-09-01  
**Files analyzed:** 15 planned implementation/export/test files  
**Analogs found:** 15 / 15 (8 direct role/data-flow matches, 7 role-compatible matches)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/agentguard/runtime/permission.py` | policy/model + utility | request-response + transform | `src/agentguard/runtime/policy.py`, `src/agentguard/runtime/loop_guard.py` | role-match |
| `src/agentguard/runtime/tool.py` | component/registry | request-response | `src/agentguard/runtime/tool.py` (self; existing Tool boundary) | exact |
| `src/agentguard/runtime/engine.py` | controller/orchestrator | event-driven + file-I/O | `src/agentguard/runtime/engine.py` (self; existing loop/resume boundary) | exact |
| `src/agentguard/domain/state.py` | model | state transition | `src/agentguard/domain/state.py` (self; existing bounded state) | exact |
| `src/agentguard/domain/runtime.py` | model | request-response | `src/agentguard/domain/runtime.py` (self; terminal result contract) | exact |
| `src/agentguard/checkpoint/model.py` | model/DTO | file-I/O | `src/agentguard/checkpoint/model.py` (self; checkpoint DTO) | exact |
| `src/agentguard/checkpoint/codec.py` | utility/codec | transform + file-I/O | `src/agentguard/checkpoint/codec.py` (self; strict JSON codec) | exact |
| `src/agentguard/events/model.py` | model | event-driven | `src/agentguard/events/model.py` (self; RuntimeEvent/EventType) | exact |
| `src/agentguard/reporting/report.py` | service/transform | event-driven → report | `src/agentguard/reporting/report.py` (self; evidence-derived report) | exact |
| `src/agentguard/runtime/__init__.py` | public API/export | request-response | `src/agentguard/runtime/__init__.py` | exact |
| `src/agentguard/checkpoint/__init__.py` | public API/export | file-I/O API | `src/agentguard/checkpoint/__init__.py` | exact |
| `src/agentguard/__init__.py` | public API/export | request-response API | `src/agentguard/__init__.py` | exact |
| `tests/unit/test_permissions.py` | test | request-response/table-driven | `tests/unit/test_retry_policy.py` and `tests/unit/test_tool_execution.py` | role-match |
| `tests/unit/test_redaction_and_digest.py` | test | deterministic transform | `tests/unit/test_loop_guard.py` | role-match |
| `tests/integration/test_permission_approval.py` | integration test | event-driven + checkpoint file-I/O | `tests/integration/test_recovery_scenarios.py` | exact |

The existing files listed as analogs are also the files expected to be modified. Keep the existing public behavior when `Runtime.permission_policy is None`; new policy-enabled paths should be additive.

## Pattern Assignments

### `src/agentguard/runtime/permission.py` (policy/model + utility, request-response + transform)

**Analogs:** `src/agentguard/runtime/policy.py` (immutable validated policy object), `src/agentguard/runtime/loop_guard.py` (canonical deterministic representation).

**Imports and dataclass validation** (`runtime/policy.py:3-6,16-33`):

```python
from dataclasses import dataclass
from enum import StrEnum

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    ...

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
```

Copy this boundary style for a frozen `PermissionPolicy` and `ApprovalDecision`: normalize sets to `frozenset`, validate strings/non-empty actor/reason and reject unknown capability labels in constructors. Use explicit `StrEnum` values like the `RetrySafety` enum (`runtime/policy.py:9-14`) so JSON/event values stay stable.

**Canonical digest pattern** (`runtime/loop_guard.py:10-21,24-35`):

```python
def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return {"__tuple__": [canonicalize(item) for item in value]}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(...)

def action_signature(action: Action) -> str:
    payload = {"tool_name": action.tool_name, "arguments": canonicalize(action.arguments)}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
```

Reuse `canonicalize` rather than `repr` or string concatenation. For `action_digest`, include `tool_name`, canonical raw arguments, sorted capabilities, `run_id`, and `step`, then prefix a `hashlib.sha256` digest with `sha256:`. Redaction must be a separate recursive projection and must never be fed into the digest.

**Error/validation pattern:** `RetryPolicy.__post_init__` raises explicit `ValueError`; `canonicalize` raises `TypeError` for unsupported values. Follow this fail-closed behavior for unknown labels, malformed decisions, and non-JSON audit values. Define structured exceptions in this module if useful (`PermissionDenied`, approval-required/digest-mismatch) and let `Runtime` map them to state/event evidence rather than swallowing them.

---

### `src/agentguard/runtime/tool.py` (component/registry, request-response)

**Analog:** existing file itself, especially `Tool` and `ToolRegistry` metadata boundary (`runtime/tool.py:32-75`).

**Tool metadata validation** (`runtime/tool.py:32-48`):

```python
@dataclass(frozen=True)
class Tool:
    name: str
    function: ToolCallable
    timeout: float | None = None
    retry_safety: RetrySafety = RetrySafety.UNKNOWN

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool name must be a non-empty string")
        if not callable(self.function):
            raise TypeError("tool function must be callable")
```

Add immutable `capabilities` metadata, normalize to a `frozenset`, and reject non-string/empty/unknown labels at this existing registration boundary. Extend `ToolRegistry.register` keyword-only metadata (`runtime/tool.py:58-71`) and preserve its in-memory name lookup (`get`, lines 73-75). Existing timeout/retry fields and executor behavior must remain unchanged; authorization belongs in `Runtime`, before `ToolExecutor.execute`, not inside the executor.

**Execution boundary to preserve** (`runtime/tool.py:93-118`): `ToolExecutor.execute` looks up the tool, returns a structured `ToolResult` for unknown tools, then invokes sync functions with `asyncio.to_thread` and async functions directly. Permission checks must prevent this method from being called for denied or pending actions.

---

### `src/agentguard/runtime/engine.py` (controller/orchestrator, event-driven + file-I/O)

**Analog:** existing file itself, current loop and explicit recovery.

**Loop ordering** (`runtime/engine.py:63-109`):

```python
action = await router.next_action(state)
if not isinstance(action, (CallTool, Finish)):
    return self._finish(state, RunStatus.FAILED, StopReason.INVALID_ACTION)
self._emit(EventType.ACTION_PROPOSED, state, ...)
if isinstance(action, Finish):
    ...
self.loop_guard.observe(action)
self._emit(EventType.TOOL_STARTED, state, tool_name=action.tool_name)
tool_result = await self.executor.execute(action, on_event=...)
```

Insert policy decision immediately after `ACTION_PROPOSED` (and before loop guard/tool-start/executor side effects as appropriate). For direct denial, emit permission evidence and call `_finish` with a structured permission stop reason without `TOOL_STARTED`. For approval, compute digest, retain a pending `CallTool`, set a non-terminal `WAITING_APPROVAL`, save a checkpoint, emit `approval_requested`, and return a resumable projection. Do not execute the pending tool.

**Resume validate-before-side-effect** (`runtime/engine.py:168-190`): load the checkpoint before emitting events or touching Router/Tool, set `resume_attempt`/event sequence, reject terminal lifecycle, emit `RESUME_STARTED`, then continue. Extend this path with an optional `ApprovalDecision`: require it for waiting checkpoints, recompute the digest against the current registry/state, emit grant/deny, and only then execute the exact pending Action before asking the Router for another Action. Digest mismatch or missing decision must reject without Router or Tool calls.

**Checkpoint/event integration** (`runtime/engine.py:192-249`): `_finish` sets terminal state, emits `RUN_FINISHED`, saves terminal lifecycle; `_emit` increments sequence and appends resume metadata; `_save_checkpoint` builds `Checkpoint` and emits `CHECKPOINT_WRITTEN`. Preserve sequence monotonicity when adding approval events and persist pending action/decision metadata in the checkpoint.

---

### `src/agentguard/domain/state.py` (model, state transition)

**Analog:** existing `RunState` (`domain/state.py:10-60`).

**Enum and bounded-state pattern** (`domain/state.py:10-23,33-53`):

```python
class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class RunState:
    ...
    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError(...)
        if self.step < 0:
            raise ValueError(...)
        if not isinstance(self.status, RunStatus):
            raise TypeError(...)
```

Add `WAITING_APPROVAL` as an explicit `RunStatus` (do not encode it as `FAILED`) and add a permission-specific `StopReason` only if the result contract needs a terminal denial. Keep `RunState.record` and bounded `recent_history` unchanged. Add a typed pending-action/approval field only if needed for Router context; make it validated and checkpoint-serializable.

---

### `src/agentguard/domain/runtime.py` (model, request-response)

**Analog:** existing terminal `RunResult` contract (`domain/runtime.py:8-25`).

```python
@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: RunStatus
    stop_reason: StopReason
    final_state: RunState

    def __post_init__(self) -> None:
        if self.run_id != self.final_state.run_id:
            raise ValueError(...)
        if self.status is RunStatus.RUNNING:
            raise ValueError("RunResult must be terminal")
```

Because waiting is non-terminal, preserve the terminal invariant by either introducing a separate resumable result/projection or explicitly updating this contract with a `WAITING_APPROVAL`-compatible type. Tests must prove an approval pause is distinguishable from failure and that existing completed/failed callers remain source-compatible.

---

### `src/agentguard/checkpoint/model.py` (model/DTO, file-I/O)

**Analog:** existing `Checkpoint` DTO and lifecycle validation (`checkpoint/model.py:32-74`).

```python
class CheckpointLifecycle(StrEnum):
    ACTIVE = "active"
    RECOVERABLE = "recoverable"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Checkpoint:
    run_id: str
    state: RunState
    max_steps: int
    pending_action: Action | None = None
    ...

    def __post_init__(self) -> None:
        if self.state.run_id != self.run_id:
            raise CheckpointValidationError(...)
        if not isinstance(self.max_steps, int) or ...:
            raise CheckpointValidationError(...)
```

Extend the DTO with an explicit waiting/approval marker, pending action digest, and compact `ApprovalDecision` projection as needed. Reuse `CheckpointValidationError`/`UnsupportedCheckpointVersionError`, validate all numeric/bool/enums, and bump `schema_version` only if the encoded shape is intentionally incompatible; otherwise preserve version-1 compatibility with optional defaulted fields. A waiting checkpoint must not be loadable through the old resume path without a decision.

---

### `src/agentguard/checkpoint/codec.py` (utility/codec, transform + file-I/O)

**Analog:** strict explicit codec (`checkpoint/codec.py:26-72,124-178,186-260`).

**JSON boundary:** `_json_value` accepts only `None`, JSON scalar types, lists, and string-keyed dicts and raises `CheckpointSerializationError` for arbitrary objects (`lines 26-40`). `_encode_action`/`_decode_action` use explicit discriminators (`lines 43-72`), while `decode_checkpoint` requires every top-level key before constructing domain objects (`lines 205-245`).

Add explicit encoders/decoders for capability sets, pending approval metadata, and `ApprovalDecision`; never serialize arbitrary objects or `__dict__`. Keep canonical `dumps_checkpoint` behavior (`lines 248-260`: `json.dumps(..., ensure_ascii=False, sort_keys=True)` plus newline) and wrap malformed JSON as `CheckpointCorruptError`.

Raw arguments may be needed in memory to recompute a digest, but persisted audit/display fields should be redacted according to the phase decision; ensure tests scan serialized bytes for known secrets where required.

---

### `src/agentguard/events/model.py` (model, event-driven)

**Analog:** existing `EventType` and immutable `RuntimeEvent` (`events/model.py:9-60`).

**Event enum/validation pattern** (`events/model.py:9-24,31-50`):

```python
class EventType(StrEnum):
    ACTION_PROPOSED = "action_proposed"
    ...
    RUN_FINISHED = "run_finished"

@dataclass(frozen=True)
class RuntimeEvent:
    ...
    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EventType):
            raise TypeError(...)
        if not isinstance(self.data, dict):
            raise TypeError(...)
        object.__setattr__(self, "data", dict(self.data))
```

Add `PERMISSION_DENIED`, `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, and `APPROVAL_DENIED` (exact names/values to be chosen consistently). Keep stable envelope fields (`event_type`, `run_id`, `step`, `timestamp`, `data`) and put tool/capability/policy/actor/reason/digest/redacted arguments in `data`. `JsonlEventSink` (`events/sinks.py:27-38`) already appends one JSON object per line; no new persistence sink is needed.

---

### `src/agentguard/reporting/report.py` (service/transform, event-driven → report)

**Analog:** existing evidence-derived report (`reporting/report.py:10-105`).

**Dataclass compatibility:** `ReliabilityReport` uses defaulted fields for Phase 4 metrics (`lines 22-28`) and `to_dict` mirrors every field (`lines 30-49`). Add defaulted approval/denial/waiting counters and evidence flags so existing callers constructing/reading reports do not break.

**Derivation pattern** (`reporting/report.py:52-105`): materialize the iterable once, derive metrics by counting `EventType` values, validate the final `RUN_FINISHED` event against `RunResult`, and return a frozen report. Derive permission/approval metrics from events (not hidden Runtime counters), count a waiting state separately from terminal failures, and include digest/approval consistency in `evidence_consistent` only when enough evidence exists.

---

### Public export files (`runtime/__init__.py`, `checkpoint/__init__.py`, `agentguard/__init__.py`)

**Analogs:** existing explicit import and `__all__` lists in all three files. `runtime/__init__.py:3-20` re-exports Tool/Executor/Runtime/policies; `checkpoint/__init__.py:3-28` re-exports DTO/errors/codec/store; root `agentguard/__init__.py:3-55` aggregates domain, runtime, events, checkpoint, evaluation, and reporting APIs. Add new permission types and exceptions to the relevant lists in the same order/style, without removing existing names.

---

### `tests/unit/test_permissions.py` (test, request-response/table-driven)

**Analogs:** `tests/unit/test_retry_policy.py` (policy validation/table cases) and `tests/unit/test_tool_execution.py:71-88` (metadata registration assertions).

Use pytest functions and `pytest.raises` for invalid labels/policies, as in `test_retry_policy.py`; register Tools with capabilities and assert immutable metadata, as existing Tool metadata tests do. Table-drive the locked examples: `{read}` allowed; `{write}` directly denied under `allowed={read}`; `{external, write}` and `{destructive, write}` approval-gated; mixed/unlabelled/unknown labels fail closed. Test policy-absent compatibility through the existing Runtime path.

---

### `tests/unit/test_redaction_and_digest.py` (test, deterministic transform)

**Analog:** `tests/unit/test_loop_guard.py:6-20` tests canonical stability and scalar/list distinctions.

Assert mapping key order does not change `action_digest`, list order and scalar types do change it, and changing tool/capability/run/step invalidates it. Test recursive dict/list/tuple redaction with case-insensitive marker names (`password`, `token`, `secret`, `api_key`, `access_key`, `private_key`, `authorization`) and extra Tool-declared sensitive fields. Assert raw secrets never appear in the redacted event projection; digest remains based on raw canonical arguments.

---

### `tests/integration/test_permission_approval.py` (integration test, event-driven + checkpoint file-I/O)

**Analog:** `tests/integration/test_recovery_scenarios.py:28-100`.

Reuse fresh deterministic Router/Tool/sink/checkpoint fixtures. The recovery test pattern uses a side-effect counter, `tmp_path`, `CheckpointStore`, `pytest.mark.asyncio`, and asserts events plus persisted JSON. Add scenarios:

1. Directly denied Tool: counter remains zero, no `TOOL_STARTED`, structured permission stop reason/event.
2. Approval-required Tool: first `run()` emits `APPROVAL_REQUESTED`, writes a waiting checkpoint, returns a resumable waiting result, and counter remains zero.
3. Approved explicit resume: same `run_id`, matching digest, `APPROVAL_GRANTED` before `TOOL_STARTED`, exactly pending Action executes before Router is called again, then normal completion.
4. Rejected approval/missing decision/digest mismatch: no executor or Router side effect after checkpoint load, `APPROVAL_DENIED` or recovery-rejected evidence, clear terminal/pending result.
5. JSONL sink projection contains redacted arguments and never known secret values.

Use the Phase 4 invariant “validation completes before any Router/Tool side effect” (`test_corrupt_checkpoint_rejected_before_tool_side_effect`) as the safety assertion.

## Shared Patterns

### Fail-closed boundary validation

**Sources:** `src/agentguard/runtime/policy.py:25-33`, `src/agentguard/domain/state.py:43-53`, `src/agentguard/checkpoint/model.py:54-74`, `src/agentguard/checkpoint/codec.py:205-245`.  
**Apply to:** capability labels, policies, decisions, waiting checkpoints, and digest inputs.

Validate Python objects in `__post_init__`, use explicit enum/error types, and reject unknown or malformed data before any Router/Tool invocation. Preserve clear exception text for tests and audit callers.

### Validate before side effect

**Sources:** `src/agentguard/runtime/engine.py:168-190`; `tests/integration/test_recovery_scenarios.py:87-100`.  
**Apply to:** approval resume, corrupt/mismatched checkpoint, and direct permission denial.

Load/decode/validate checkpoint and approval digest first; only after all checks pass may Runtime emit grant/started events or call the executor. Test using a side-effect counter and Router call counter.

### Event evidence is append-only and report-derived

**Sources:** `src/agentguard/events/model.py:31-60`, `src/agentguard/events/sinks.py:17-38`, `src/agentguard/reporting/report.py:52-105`.  
**Apply to:** permission and approval branches.

Extend `EventType` and emit structured JSON-safe data through the existing sink. Derive report metrics from event streams and retain existing envelope fields; do not add a second audit log or hidden metric counter.

### Deterministic, explicit JSON

**Sources:** `src/agentguard/runtime/loop_guard.py:10-35`, `src/agentguard/checkpoint/codec.py:26-40,248-260`.  
**Apply to:** action digest, approval binding, pending checkpoint state, and redacted audit payload.

Canonicalize mappings with sorted keys, preserve list order/types, serialize only known primitives/containers, and use `ensure_ascii=False` plus `sort_keys=True` for persisted output.

### Public API compatibility

**Sources:** `src/agentguard/__init__.py:3-55`, package `__init__.py` files.  
**Apply to:** all newly public permission classes/events/statuses.

Add exports without changing existing constructor defaults. A `None` permission policy must bypass new authorization and preserve Phase 1–4 test behavior.

## No Analog Found

No file lacks an analog. `runtime/permission.py` is new, but its policy object and canonicalization/redaction utilities have strong role-compatible patterns in `runtime/policy.py` and `runtime/loop_guard.py`. Approval-specific lifecycle semantics are new; use the existing engine/checkpoint recovery boundaries and the Phase 5 research recommendations rather than introducing a new persistence framework.

## Metadata

**Analog search scope:** `src/agentguard/{runtime,domain,checkpoint,events,reporting}`, `tests/{unit,integration}`.  
**Files scanned:** 20 source/test files (including analog tests and package exports).  
**Pattern extraction date:** 2026-09-01
