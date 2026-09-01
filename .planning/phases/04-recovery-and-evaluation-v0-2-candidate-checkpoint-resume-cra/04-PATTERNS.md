# Phase 4: Recovery and Evaluation - Pattern Map

**Mapped:** 2026-09-01  
**Files analyzed:** 18 proposed/new or modified files  
**Analogs found:** 15 / 18 (the checkpoint and evaluation packages are new domains; existing Runtime, domain, event, reporting, and test files provide strong integration analogs)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/agentguard/checkpoint/model.py` | model/DTO | transform (domain objects → checkpoint payload) | `src/agentguard/domain/state.py`, `domain/results.py` | role-match |
| `src/agentguard/checkpoint/codec.py` | utility/codec | transform, request-response | `src/agentguard/events/model.py` (`to_dict`) | role-match |
| `src/agentguard/checkpoint/store.py` | storage/service | file-I/O request-response | `src/agentguard/events/sinks.py::JsonlEventSink` | role-match |
| `src/agentguard/checkpoint/__init__.py` | package export | — | `src/agentguard/events/__init__.py` | exact |
| `src/agentguard/runtime/engine.py` | runtime/controller (modified) | request-response loop | existing `Runtime.run()` | exact |
| `src/agentguard/events/model.py` | event model (modified) | event-driven append-only | existing `RuntimeEvent`/`EventType` | exact |
| `src/agentguard/events/sinks.py` | event persistence (possibly modified) | file-I/O append | `JsonlEventSink` | exact |
| `src/agentguard/reporting/report.py` | reporting/transform (modified) | transform events → summary | existing `build_report()` | exact |
| `src/agentguard/evaluation/scenarios.py` | model/registry | factory/event-driven setup | `runtime/router.py::ScriptedRouter` | role-match |
| `src/agentguard/evaluation/runner.py` | service/runner | batch request-response + transform | `runtime/engine.py::Runtime.run` and `reporting/report.py` | role-match |
| `src/agentguard/evaluation/__init__.py` | package export | — | `src/agentguard/events/__init__.py` | exact |
| `src/agentguard/__init__.py` | public API export (modified) | — | current exports at lines 3-31 | exact |
| `tests/unit/test_checkpoint.py` | unit test | transform/validation | `tests/unit/test_domain_models.py` | exact |
| `tests/unit/test_checkpoint_store.py` | unit test | file-I/O | `tests/unit/test_event_sinks.py` | exact |
| `tests/integration/test_recovery_scenarios.py` | integration test | request-response + fault/recovery | `tests/integration/test_runtime_loop.py` | exact |
| `tests/unit/test_evaluation.py` (if split from integration tests) | unit test | batch transform | `tests/unit/test_report.py` | role-match |
| `learning/zh-CN/04-checkpoint-recovery.md` | documentation/learning note | narrative over code/evidence | Phase 2/3 learning-note convention | no code analog |
| `learning/en/04-checkpoint-recovery.md` | documentation/learning note | narrative over code/evidence | Phase 2/3 learning-note convention | no code analog |

The planner may combine `test_evaluation.py` into `test_recovery_scenarios.py`; no second runner is required. A benchmark CLI/result file is optional and has no established source analog.

## Pattern Assignments

### `src/agentguard/checkpoint/model.py` (model/DTO, transform)

**Analog:** `src/agentguard/domain/state.py` and `src/agentguard/domain/results.py`.

**Dataclass and enum pattern** (`state.py:10-23, 24-41`):

```python
class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class RunState:
    run_id: str
    step: int = 0
    status: RunStatus = RunStatus.RUNNING
    last_result: ToolResult | None = None
    recent_history: list[HistoryEntry] = field(default_factory=list)
```

Use the same Python 3.11 `StrEnum`/dataclass style for `CheckpointLifecycle` (`active`, `recoverable`, `completed`, `failed`) and a typed `Checkpoint` DTO. Keep fields explicit (schema version, run ID, state, runtime config, event position, resume attempt, optional latest action/result context) instead of persisting `__dict__`.

**Validation pattern** (`state.py:43-53`, `results.py:35-60`):

```python
def __post_init__(self) -> None:
    if not isinstance(self.run_id, str) or not self.run_id.strip():
        raise ValueError("run_id must be a non-empty string")
    if self.step < 0:
        raise ValueError("step cannot be negative")
    if not isinstance(self.status, RunStatus):
        raise TypeError("status must be a RunStatus")
```

Apply equivalent checks to schema version, lifecycle enum, non-negative step/event position/resume attempt, and valid `RunState`/`RunResult` invariants. Preserve bounded history by reconstructing `RunState` with `history_limit`; do not add full event history to the DTO.

### `src/agentguard/checkpoint/codec.py` (utility/codec, transform)

**Analog:** `src/agentguard/events/model.py`.

**Stable JSON projection** (`events/model.py:48-56`):

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "event_type": self.event_type.value,
        "run_id": self.run_id,
        "step": self.step,
        "timestamp": self.timestamp,
        "data": self.data,
    }
```

Implement explicit `encode_checkpoint()`/`decode_checkpoint()` (and small helpers for `CallTool`, `Finish`, `ToolResult`, `HistoryEntry`) returning JSON-compatible primitives. Tag action variants (`action_type`) and serialize enum values with `.value`; use `json.dumps(..., ensure_ascii=False, sort_keys=True)` for deterministic output. Validate raw JSON shape and required keys before constructing domain objects, then let their `__post_init__` enforce invariants. Catch `json.JSONDecodeError` and map it to a distinct `CheckpointCorruptError`; missing/type-invalid fields map to `CheckpointValidationError`; unsupported `schema_version` maps to `UnsupportedCheckpointVersionError`. Do not stringify arbitrary `ToolResult.value`; reject non-JSON-compatible values with a serialization error.

### `src/agentguard/checkpoint/store.py` (storage/service, file-I/O)

**Analog:** `src/agentguard/events/sinks.py::JsonlEventSink` (`lines 27-38`).

```python
class JsonlEventSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: RuntimeEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(line)
            file.write("\n")
```

`CheckpointStore` should similarly normalize `str | Path`, create parent directories, and expose clear `save(checkpoint)`/`load(path)` boundaries. Unlike append-only JSONL, save must use same-directory temp file + JSON dump + newline + flush/`os.fsync` + `os.replace`; remove only the temporary file on failure and never truncate the canonical checkpoint. Keep the original file on load/validation failure. Expose path convention (`{run_id}.json`) and preserve lifecycle status on terminal updates.

### `src/agentguard/runtime/engine.py` (modified Runtime, request-response loop)

**Analog:** current `Runtime.run()` (`engine.py:35-140`). The loop is the single execution path to preserve for `resume()`.

**Post-step integration boundary** (`engine.py:83-90`):

```python
tool_result = await self.executor.execute(
    action,
    on_event=lambda event_type, data: self._emit(event_type, state, **data),
)
state.record(action, tool_result)
state.step += 1
```

Place checkpoint commit after the complete state mutation/step increment (and before the next Router decision). Inject `SimulatedCrash` only at the explicit `after_tool_before_checkpoint` hook; default construction must leave the hook disabled. `Finish` also needs a completed-step checkpoint/lifecycle update before `_finish()` if the design treats terminal steps as committed.

**Reuse executor and terminal evidence** (`engine.py:142-165`):

```python
def _finish(...):
    state.status = status
    self._emit(EventType.RUN_FINISHED, state, status=status.value, stop_reason=reason.value)
    return RunResult(... final_state=state)
```

Add explicit `async resume(checkpoint_path, router, ...)` that loads/validates the checkpoint before emitting recovery events or invoking `ToolExecutor`; reconstruct `RunState`, preserve `run_id`, initialize event position, increment `resume_attempt`, and enter the same internal loop. Do not scan checkpoint directories from `run()`. Mark replay/duplicate possibility in event data and report metrics. Keep max-step, loop guard, timeout, retry, and `_finish()` semantics unchanged.

### `src/agentguard/events/model.py` (modified event model, event-driven)

**Analog:** `RuntimeEvent` (`events/model.py:27-46`).

```python
@dataclass(frozen=True)
class RuntimeEvent:
    event_type: EventType
    run_id: str
    step: int
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now_iso)
```

Extend `EventType` with checkpoint/recovery facts (for example checkpoint written, resume started, duplicate possible, recovery rejected) while preserving existing string values and `to_dict()` shape. If adding a sequence field, make it optional/backward-compatible and assign it monotonically from Runtime/sink using the checkpointed event position; always include `run_id`, `step`, `resume_attempt`, and duplicate metadata in recovery event `data`. Retain defensive copying (`object.__setattr__(..., dict(self.data))`) and enum/type checks.

### `src/agentguard/events/sinks.py` (possibly modified persistence, file-I/O)

**Analog:** existing `EventSink` Protocol and ordered in-memory sink (`sinks.py:10-25`).

```python
class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None: ...

class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)
```

Keep the sink synchronous and append-only. Recovery can use a fresh sink after process restart; initialize sequence metadata from the checkpoint rather than resetting the logical run. Preserve `JsonlEventSink` one-event-per-line behavior and compatibility with existing CLI tests.

### `src/agentguard/reporting/report.py` (modified report transform)

**Analog:** `ReliabilityReport` and `build_report()` (`report.py:10-35, 38-73`).

```python
event_list = tuple(events)
event_dicts = tuple(event.to_dict() for event in event_list)
finished = [event for event in event_list if event.event_type is EventType.RUN_FINISHED]
...
tool_calls = sum(event.event_type is EventType.TOOL_STARTED for event in event_list)
retry_count = sum(event.event_type is EventType.RETRY_SCHEDULED for event in event_list)
```

Preserve the frozen dataclass + `to_dict()` projection and existing V0.1 fields. Add Phase 4 reliability fields (checkpoint writes/success, recovery success, duplicate-possible Tool executions, crash-to-recovery steps, final-state correctness) derived from appended recovery events/metadata. Keep `evidence_consistent` logic and avoid token/cost/semantic metrics. Use immutable tuples internally and machine-readable JSON values.

### `src/agentguard/evaluation/scenarios.py` (model/registry, factory/event-driven)

**Analog:** `ScriptedRouter` (`runtime/router.py:17-26`) and deterministic test-local Router classes (`tests/integration/test_runtime_loop.py:17-41`).

```python
class ScriptedRouter:
    def __init__(self, actions: Sequence[Action]) -> None:
        self._actions = tuple(actions)

    async def next_action(self, state: RunState) -> Action:
        if state.step >= len(self._actions):
            raise RuntimeError("scripted router has no remaining actions")
        return self._actions[state.step]
```

Define an immutable `ScenarioDefinition` with name/description, a factory that creates fresh `RunState`, Router, ToolExecutor/registry, checkpoint path and optional crash hook, expected terminal state/predicate, and metric names. Register three deterministic scenarios (clean completion, crash after Tool before checkpoint then explicit resume, corrupt checkpoint rejection). Factories must return fresh mutable objects per run; never share Tool call counters or Routers across scenario executions.

### `src/agentguard/evaluation/runner.py` (service/runner, batch request-response)

**Analogs:** `Runtime.run()` for async orchestration (`engine.py:35-140`) and `build_report()` for derived metrics (`report.py:38-73`).

Run a selected scenario factory, capture its sink/events, optionally catch `SimulatedCrash`, call explicit `Runtime.resume()`, then compute a JSON-serializable reliability result. Count checkpoint writes and successes, recovery success, duplicate-possible executions, crash-to-recovery steps, and final-state correctness from evidence rather than hidden counters. Keep execution sequential/deterministic and expose a registry lookup that fails clearly for unknown scenario names.

### Package exports (`checkpoint/__init__.py`, `evaluation/__init__.py`, root `__init__.py`)

**Analog:** `events/__init__.py:3-12` and root `src/agentguard/__init__.py:3-31`.

```python
from .model import EventType, RuntimeEvent
from .sinks import EventSink, InMemoryEventSink, JsonlEventSink

__all__ = ["EventSink", "EventType", "InMemoryEventSink", "JsonlEventSink", "RuntimeEvent"]
```

Use explicit imports and `__all__`; expose only the stable checkpoint/evaluation contracts and new exception classes. Keep module imports free of side effects so existing `import agentguard` remains valid.

### `tests/unit/test_checkpoint.py` (unit, transform/validation)

**Analog:** `tests/unit/test_domain_models.py` (`lines 15-35, 56-110`).

```python
@pytest.mark.parametrize("factory", [...])
def test_actions_reject_invalid_values(factory) -> None:
    with pytest.raises((ValueError, TypeError)):
        factory()
```

Test round-trip of supported `RunState`/Action/ToolResult values, enum tags, bounded history, required-field rejection, corrupt JSON, unsupported schema version, and rejection of non-JSON `ToolResult.value`. Assert decode occurs before any executor/tool call (use a side-effect counter).

### `tests/unit/test_checkpoint_store.py` (unit, file-I/O)

**Analog:** `tests/unit/test_event_sinks.py` (`lines 6-43`).

```python
def test_jsonl_sink_writes_one_parseable_event_per_line(tmp_path) -> None:
    path = tmp_path / "events" / "run.jsonl"
    sink = JsonlEventSink(path)
    sink.emit(RuntimeEvent(...))
    event = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert event["event_type"] == "tool_failed"
```

Use `tmp_path`, `Path.read_text`, and `json.loads` to assert checkpoint file creation, deterministic fields, parent directory creation, atomic-save replacement, lifecycle updates, and preservation of the previous valid file when a write or load fails. Avoid platform-specific timing or process-kill assertions.

### `tests/integration/test_recovery_scenarios.py` (integration, request-response/fault recovery)

**Analog:** `tests/integration/test_runtime_loop.py` (`lines 43-68`, `136-186`).

```python
@pytest.mark.asyncio
async def test_runtime_completes_echo_then_finish() -> None:
    sink = InMemoryEventSink()
    runtime = Runtime(ToolExecutor(ToolRegistry({"echo": echo})), event_sink=sink)
    result = await runtime.run(ResultDrivenRouter(), RunState("run-success"))
    assert result.status is RunStatus.COMPLETED
    assert [event.event_type for event in sink.events] == [...]
```

Build deterministic async scenarios with scripted Routers and local Tools. Assert clean completion writes checkpoints; injected `after_tool_before_checkpoint` raises `SimulatedCrash` while leaving the previous checkpoint intact, and `resume()` reuses `run_id`, increments `resume_attempt`, may execute the Tool twice, and reaches expected final state; corrupt checkpoint fails before Tool side effects and preserves the original bytes. Assert ordered recovery events and report metrics.

### `learning/zh-CN/04-checkpoint-recovery.md` and `learning/en/04-checkpoint-recovery.md` (documentation)

**Analog:** existing Phase 2/3 learning notes and decision docs (same bilingual, evidence-grounded convention). Explain the post-step atomic boundary, at-least-once replay, validation-before-side-effect rule, explicit resume, and measured scenario results. Keep Chinese and English facts aligned; do not claim exactly-once or process-level cancellation.

## Shared Patterns

### Typed boundary validation

**Sources:** `domain/state.py:43-53`, `domain/results.py:35-60`, `events/model.py:37-46`, `runtime/tool.py:41-47`. Apply to checkpoint DTOs, codec inputs, scenario definitions, and new exceptions. Validate before side effects; preserve enum identity and non-empty IDs.

### Explicit JSON projection

**Source:** `events/model.py:48-56`. Use explicit field maps, enum `.value`, `ensure_ascii=False`, and deterministic key ordering. Never serialize raw exception objects or arbitrary `__dict__` state.

### Single Runtime execution path

**Sources:** `runtime/engine.py:35-140` and `runtime/tool.py:93-210`. `resume()` reconstructs state then invokes the existing Router and `ToolExecutor`; do not duplicate timeout/retry/cancellation logic or create an alternate loop.

### Append-only evidence

**Sources:** `events/sinks.py:10-38`, `reporting/report.py:41-73`. Emit structured events in order, append resumed events with shared `run_id` and `resume_attempt`, then derive reports from events plus `RunResult`.

### Deterministic tests

**Sources:** `tests/integration/test_runtime_loop.py` scripted Router classes and `tests/unit/test_event_sinks.py`/`test_domain_models.py` use of `tmp_path`, direct assertions, and `pytest.mark.asyncio`. Keep fault injection explicit and avoid sleeps/process races.

## No Analog Found

| File/Concern | Role | Data Flow | Reason |
|---|---|---|---|
| `src/agentguard/checkpoint/model.py` lifecycle DTO | model | transform | No checkpoint abstraction exists; copy domain dataclass/enum validation. |
| `src/agentguard/checkpoint/codec.py` decode/validation | utility | transform | Existing `to_dict()` only serializes events; no inverse codec. Use explicit stdlib JSON. |
| `src/agentguard/checkpoint/store.py` atomic replacement | storage | file-I/O | JSONL sink appends but does not atomically replace; follow research's tempfile + `os.replace` pattern. |
| `src/agentguard/evaluation/scenarios.py` registry | model/registry | factory | No registry abstraction exists; adapt `ScriptedRouter` and fresh test fixtures. |
| `src/agentguard/evaluation/runner.py` reliability benchmark | service | batch | No benchmark runner exists; compose Runtime and report APIs. |
| `learning/*/04-checkpoint-recovery.md` | docs | narrative | No code analog; follow bilingual Phase 2/3 learning-note structure. |

## Metadata

**Analog search scope:** `src/agentguard/{domain,runtime,events,reporting}`, `tests/{unit,integration}`, package exports, and Phase 1–3 plans.  
**Files scanned:** 16 source/test analog files plus package/config files.  
**Pattern extraction date:** 2026-09-01
