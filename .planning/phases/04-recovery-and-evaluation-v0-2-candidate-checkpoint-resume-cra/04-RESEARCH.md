# Phase 4: Recovery and Evaluation (v0.2 candidate) - Research

**Researched:** 2026-09-01  
**Domain:** Local Python Runtime checkpointing, explicit async resume, deterministic fault injection, and reliability evaluation  
**Confidence:** HIGH for existing-code integration; MEDIUM for filesystem durability details

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Checkpoint contents and write timing
- **D-01:** Persist only the minimum state required to choose and execute the next Action: `run_id`, `RunState`, current `step`, latest Action/ToolResult context, relevant runtime configuration, and event position/sequence metadata.
- **D-02:** Write a checkpoint after each complete Runtime step: Action chosen, Tool execution finished, result recorded, and step incremented. Use an atomic write boundary.
- **D-03:** The first version explicitly provides at-least-once semantics. If a crash occurs after Tool execution but before checkpoint persistence, resume may execute that Action again.

### Storage and lifecycle
- **D-04:** Use one local JSON checkpoint file per `run_id`, written through a temporary file and atomic replacement.
- **D-05:** Include a `schema_version`; do not introduce Redis, a database, or distributed coordination.
- **D-06:** Retain checkpoint files after completion or terminal failure and update their lifecycle status (`active`, `recoverable`, `completed`, or `failed`). Automatic cleanup is deferred.

### Crash and resume behavior
- **D-07:** Provide deterministic, injectable crash points, especially `after_tool_before_checkpoint`, through a `SimulatedCrash` mechanism that is absent from the normal default path.
- **D-08:** Expose an explicit `resume(checkpoint_path=..., router=...)` API. Normal `run()` must not scan for or automatically resume old checkpoints.
- **D-09:** Resume must validate JSON, required fields, and schema version before executing any Tool. Corrupt, incomplete, or unsupported checkpoints are rejected with distinct errors; the original file remains available for diagnosis.
- **D-10:** Reuse the same logical `run_id` across recovery attempts. Increment `resume_attempt` for each recovery and append events rather than overwriting prior evidence. Mark possible duplicate execution explicitly.

### Evaluation scope
- **D-11:** Measure Runtime reliability only: checkpoint write count/success, recovery success rate, possible duplicate Tool executions, steps from crash to recovery completion, and final-state correctness.
- **D-12:** Implement a small scenario registry shared by tests and benchmark/report generation. Each scenario defines its name, initial state, Router/Tool setup, fault injection, expected terminal state, and metrics.
- **D-13:** Start with three deterministic scenarios: clean completion, Tool-complete/crash-before-checkpoint followed by resume, and corrupt-checkpoint safe rejection.

### the agent's Discretion
The exact JSON field layout, checkpoint filename convention, exception class hierarchy, event names, metric aggregation structure, and test fixture organization are open to standard, inspectable Python approaches as long as the decisions above remain true.

### Deferred Ideas (OUT OF SCOPE)
- Exactly-once execution via idempotency keys and durable deduplication.
- Automatic checkpoint discovery and cleanup policies.
- Process-level forced termination and rollback of external side effects.
- Redis/database/distributed checkpoint stores.
- Token, cost, semantic-quality, or real-LLM throughput metrics.
- Parallel scheduling, permission workflows, and framework adapters remain future roadmap work.
</user_constraints>

## Summary

The existing Runtime is a single async loop around typed `RunState`, `CallTool`/`Finish` actions, `ToolExecutor`, and append-only `RuntimeEvent` sinks [VERIFIED: codebase grep]. Phase 4 should add a small checkpoint boundary around that loop rather than introduce a second execution engine: serialize a validated projection of state after each completed step, then have `resume()` reconstruct the same objects and call the same Router/executor path [VERIFIED: codebase grep].

Use only Python standard-library facilities (`dataclasses`, `enum`, `json`, `pathlib`, `tempfile`, `os`, `asyncio`) so files remain inspectable and the project keeps its no-service setup [VERIFIED: pyproject.toml; .planning/REQUIREMENTS.md]. The safe filesystem pattern is a temporary file in the destination directory, JSON dump, flush/`fsync`, then `os.replace`; `os.replace` is the atomic replacement primitive documented by Python [CITED: https://docs.python.org/3/library/os.html#os.replace]. Treat durability after a power loss as a documented best-effort boundary; the project only needs deterministic local crash tests, not a distributed durable store [ASSUMED].

**Primary recommendation:** Add a `CheckpointStore`/codec with explicit schema validation and atomic JSON replacement, integrate hooks at the post-step boundary, expose `Runtime.resume()`, and drive three deterministic scenarios from one registry that emits reliability metrics and recovery evidence.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Checkpoint JSON schema/codec | API / Backend (Runtime library) | Database / Storage (filesystem) | Runtime owns the object contract; filesystem only stores bytes [VERIFIED: codebase grep]. |
| Atomic checkpoint persistence | Database / Storage (local filesystem) | API / Backend | Store owns temp-file replacement; Runtime decides when to commit [CITED: https://docs.python.org/3/library/os.html#os.replace]. |
| Explicit resume and state reconstruction | API / Backend | — | Resume must validate before invoking Router or Tool [VERIFIED: 04-CONTEXT.md]. |
| Crash injection | API / Backend (test/runtime hook) | — | Fault point is a deterministic Runtime concern and must be inert by default [VERIFIED: 04-CONTEXT.md]. |
| Scenario registry and reliability metrics | API / Backend (evaluation package) | Storage (JSON result) | Registry supplies factories; evaluator computes run/recovery measurements [VERIFIED: 04-CONTEXT.md]. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---|---|---|---|
| Python standard library `dataclasses`/`enum` | Python >=3.11 (project requirement) | Typed checkpoint DTOs and lifecycle enums | Existing domain contracts are dataclasses and `StrEnum`; reuse them rather than introduce a schema package [VERIFIED: pyproject.toml; src/agentguard/domain]. |
| `json` | Python stdlib | Deterministic, human-readable checkpoint and scenario-result encoding | `json.JSONDecodeError` gives a distinct parse failure and `json.dump`/`dumps` supports sorted keys [CITED: https://docs.python.org/3/library/json.html]. |
| `pathlib.Path`, `tempfile`, `os.replace` | Python stdlib | Same-directory temporary file and atomic replacement | Standard filesystem APIs; `os.replace` replaces destination atomically when supported by the OS [CITED: https://docs.python.org/3/library/pathlib.html; https://docs.python.org/3/library/tempfile.html; https://docs.python.org/3/library/os.html#os.replace]. |
| `asyncio` | Python stdlib | Async `run`/`resume` and deterministic crash hook | Runtime and Router are already async protocols [VERIFIED: src/agentguard/runtime/engine.py; src/agentguard/runtime/router.py]. |

### Supporting

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| `pytest` + `pytest-asyncio` | pytest 8.3.5 observed; plugin behavior follows existing config | Unit/integration tests for checkpoint, resume, and scenarios | Use existing test style; no new test framework [VERIFIED: `pytest --version`; pyproject.toml]. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| JSON + stdlib codec | `pickle` | Pickle can serialize arbitrary Python objects but executes code on load; unsafe for a user-provided checkpoint and not inspectable [CITED: https://docs.python.org/3/library/pickle.html]. |
| Local file store | Redis/SQL database | Adds services and coordination that the locked Phase 4 boundary excludes [VERIFIED: 04-CONTEXT.md]. |
| Explicit `resume()` | Auto-discovery on `run()` | Auto-discovery can trigger stale Tool calls; explicit API preserves operator intent [VERIFIED: 04-CONTEXT.md]. |
| At-least-once replay | Exactly-once/idempotency keys | Exactly-once needs durable deduplication and external side-effect contracts, explicitly deferred [VERIFIED: 04-CONTEXT.md]. |

**Installation:** No external runtime package is required. Use the project’s existing Python environment; run tests with `PYTHONPATH=src pytest -q` [VERIFIED: pyproject.toml; existing commands].

## Architecture Patterns

### System Architecture Diagram

```text
run(router, initial_state)
        |
        v
  Runtime loop: propose Action -> execute Tool -> record result -> increment step
        |                                      |
        | completed step                       | injected after_tool_before_checkpoint
        v                                      v
  CheckpointCodec -> CheckpointStore       SimulatedCrash (no checkpoint for this step)
        |                                      |
        +--> temp JSON + flush/fsync + os.replace  |
                                                   v
                                      explicit resume(path, router)
                                                   |
                                  validate JSON/schema BEFORE Tool
                                                   |
                              reconstruct state + resume_attempt += 1
                                                   |
                              same Runtime loop (possible duplicate)
                                                   |
                                         RunResult + events + report

scenario registry --> fresh factories --> run/resume --> JSON evaluation result
```

### Recommended Project Structure

```text
src/agentguard/
├── checkpoint/
│   ├── model.py       # lifecycle DTO and schema_version
│   ├── codec.py       # Action/ToolResult/RunState JSON projection + validation
│   └── store.py       # atomic write/read, corruption/version errors
├── evaluation/
│   ├── scenarios.py   # ScenarioDefinition and registry
│   └── runner.py      # scenario execution and reliability metrics
├── runtime/
│   └── engine.py      # post-step checkpoint hook and explicit resume()
└── events/
    └── model.py       # recovery/checkpoint event types
tests/
├── unit/test_checkpoint.py
├── unit/test_checkpoint_store.py
└── integration/test_recovery_scenarios.py
```

### Pattern 1: Typed JSON projection (not generic object serialization)
**What:** Convert each domain object to a plain JSON object with explicit enum values and tagged action/result variants; validate types and required keys before constructing dataclasses [VERIFIED: existing `to_dict()` patterns in src/agentguard/events/model.py].

**When to use:** Every checkpoint write/read. Reject unsupported `ToolResult.value` values instead of silently stringifying them [ASSUMED].

```python
payload = {
    "schema_version": 1,
    "lifecycle": "active",
    "run_id": state.run_id,
    "state": {
        "step": state.step,
        "status": state.status.value,
        "history_limit": state.history_limit,
        "last_result": encode_tool_result(state.last_result),
        "recent_history": [encode_history(item) for item in state.recent_history],
    },
    "runtime": {"max_steps": runtime.max_steps},
    "event_position": event_sequence,
    "resume_attempt": resume_attempt,
}
json.dumps(payload, ensure_ascii=False, sort_keys=True)
```

### Pattern 2: Atomic checkpoint commit
**What:** Create a unique temp file beside the final path, write deterministic JSON plus newline, flush and `os.fsync` the file, then call `os.replace(temp, final)`; remove only the temp file on failure [CITED: https://docs.python.org/3/library/os.html#os.replace; https://docs.python.org/3/library/tempfile.html].

**When to use:** The post-step commit boundary and lifecycle status updates. Never truncate the canonical file before the replacement succeeds [ASSUMED].

### Pattern 3: Validate-before-side-effect resume
**What:** `resume()` reads and validates the entire checkpoint (JSON syntax, schema version, required fields, enum values, run ID, and state invariants) before constructing an executor call; only then emits `RESUME_STARTED` and enters the loop [VERIFIED: D-09].

**When to use:** Every explicit resume attempt, including corrupt or hand-edited files.

### Pattern 4: Deterministic crash window and duplicate evidence
**What:** Inject a hook immediately after `state.record(...)`/step increment and before checkpoint write. Raise `SimulatedCrash`; leave the previous checkpoint untouched. On resume, include `resume_attempt` and `duplicate_possible=true` in recovery events/report [VERIFIED: D-03, D-07, D-10].

**When to use:** Integration scenario proving at-least-once semantics. The normal Runtime path must not install this hook by default.

### Pattern 5: Scenario factory registry
**What:** Register immutable scenario definitions whose factory returns fresh Router, ToolExecutor, initial state, checkpoint path, fault injection, expected terminal state, and metric names. The test and benchmark runner consume the same definition [VERIFIED: D-12].

**When to use:** Three initial deterministic scenarios; avoid shared mutable Router counters between runs.

### Anti-Patterns to Avoid

- **Serializing `__dict__` blindly:** loses enum/tag information and permits schema drift; use explicit codecs [VERIFIED: existing typed models; ASSUMED risk].
- **Writing directly to the canonical file:** a crash during `json.dump` can leave truncated JSON; use same-directory temp + replace [CITED: https://docs.python.org/3/library/os.html#os.replace].
- **Executing a Tool before checkpoint validation:** malformed data could trigger an unintended side effect; validate all fields first [VERIFIED: D-09].
- **Resetting `run_id` on resume:** breaks event/report correlation; preserve logical run ID and increment `resume_attempt` [VERIFIED: D-10].
- **Using process kill as the only crash test:** timing is flaky and obscures the exact at-least-once window; use injectable deterministic crash points [VERIFIED: D-07].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Atomic replacement | Custom lock/rename protocol | `tempfile` + `os.replace` | OS/filesystem primitive handles replacement semantics [CITED: https://docs.python.org/3/library/os.html#os.replace]. |
| JSON parsing | Regex/manual parser | `json.loads` and catch `JSONDecodeError` | Correct escaping and syntax handling are non-trivial [CITED: https://docs.python.org/3/library/json.html]. |
| Async execution | Separate sync resume loop | Existing `Runtime.run`/`ToolExecutor.execute` | Preserves timeout, retry, and cancellation semantics already tested [VERIFIED: src/agentguard/runtime/tool.py]. |
| Arbitrary object persistence | `pickle` or `repr` fallback | Explicit JSON-compatible domain projection | Prevents code execution and non-reproducible values [CITED: https://docs.python.org/3/library/pickle.html; ASSUMED]. |

**Key insight:** Recovery correctness is primarily a boundary/ordering problem. Keeping one execution path and making the checkpoint schema explicit makes duplicate execution and evidence gaps observable without introducing a service dependency [VERIFIED: 04-CONTEXT.md; existing Runtime].

## Common Pitfalls

### Pitfall 1: Checkpointing too early
**What goes wrong:** A checkpoint can contain an Action without its ToolResult or an unincremented step, so resume decisions do not match Router state [ASSUMED].  
**Why it happens:** Hook is placed before `state.record`/step increment rather than after the complete step [VERIFIED: engine.py].  
**How to avoid:** Commit only after Action, Tool result, state mutation, and step increment; test the crash hook immediately before the commit [VERIFIED: D-02, D-07].  
**Warning signs:** Resumed Router sees `last_result=None` despite a completed Tool.

### Pitfall 2: `ToolResult.value` is not JSON-compatible
**What goes wrong:** `json.dumps` raises `TypeError` or a custom conversion loses type fidelity [CITED: https://docs.python.org/3/library/json.html].  
**Why it happens:** Domain allows `object | None` for values [VERIFIED: src/agentguard/domain/results.py].  
**How to avoid:** Define supported JSON scalar/list/dict values and raise a checkpoint serialization error for others; add a test [ASSUMED].  
**Warning signs:** Checkpoint write fails after a Tool succeeded.

### Pitfall 3: Treating `asyncio.TimeoutError` as a checkpoint crash or swallowing cancellation
**What goes wrong:** Resume tests become non-deterministic or hang when an async Tool suppresses cancellation [VERIFIED: Phase 2 learning; src/agentguard/runtime/tool.py].  
**Why it happens:** Reimplementing Tool execution in recovery instead of invoking `ToolExecutor` [VERIFIED: src/agentguard/runtime/tool.py].  
**How to avoid:** Resume through the same executor and only inject `SimulatedCrash` at the checkpoint hook [VERIFIED: D-07].

### Pitfall 4: Event sequence drift across resume
**What goes wrong:** Appended events have duplicate sequence numbers or reports cannot tell original vs recovery attempts [ASSUMED].  
**Why it happens:** In-memory sink resets on process restart and event position is not persisted [VERIFIED: D-01, D-10].  
**How to avoid:** Persist `event_position`/sequence in checkpoint; initialize the resumed event sequence from it, and emit `resume_attempt` on recovery events [VERIFIED: D-01, D-10].

### Pitfall 5: Corrupt checkpoint accidentally falls back to defaults
**What goes wrong:** Missing `max_steps`/state fields are silently filled and a Tool runs with an unintended state [VERIFIED: D-09].  
**Why it happens:** Decoder treats absent keys as optional defaults [ASSUMED].  
**How to avoid:** Required-field validation with distinct parse, schema, and version exceptions; leave original file untouched [VERIFIED: D-09].

## Code Examples

### Atomic JSON write
```python
from pathlib import Path
import json, os, tempfile

def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise
```
Source: Python `os.replace`, `tempfile`, and `json` documentation [CITED: https://docs.python.org/3/library/os.html#os.replace; https://docs.python.org/3/library/tempfile.html; https://docs.python.org/3/library/json.html].

### Resume validation boundary
```python
def load_checkpoint(path: Path) -> Checkpoint:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckpointCorruptError(path) from exc
    validate_required_fields(raw)          # no defaults for required keys
    if raw["schema_version"] != 1:
        raise UnsupportedCheckpointVersionError(raw["schema_version"])
    return decode_checkpoint(raw)           # constructs RunState only now
```
Source: `json.loads`/`JSONDecodeError` behavior [CITED: https://docs.python.org/3/library/json.html]; validation order is required by D-09 [VERIFIED: 04-CONTEXT.md].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Re-run the whole agent after a process failure | Persist a minimal state snapshot and explicitly resume | Phase 4 design decision (2026-09-01) [VERIFIED: 04-CONTEXT.md] | Bounded replay and inspectable duplicate evidence. |
| In-memory-only execution evidence | Append recovery events with a shared `run_id` and `resume_attempt` | Phase 4 design decision (2026-09-01) [VERIFIED: 04-CONTEXT.md] | Reports can distinguish original and resumed attempts. |
| Service-backed checkpoint coordination | Local JSON + atomic replacement | Phase 4 design decision (2026-09-01) [VERIFIED: 04-CONTEXT.md] | Keeps the learning slice runnable without infrastructure. |

**Deprecated/outdated:** None in this project; Phase 4 is adding the first checkpoint capability. Exactly-once, automatic discovery/cleanup, and distributed stores are explicitly deferred [VERIFIED: 04-CONTEXT.md].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | `ToolResult.value` will be restricted to JSON-compatible scalars/containers rather than adding a custom binary serializer. | Pattern 1; Pitfall 2 | A Tool returning a custom object would need a documented adapter or checkpoint write would fail. |
| A2 | File `fsync` plus `os.replace` is sufficient durability for deterministic local tests; directory fsync and crash-consistency guarantees are not required. | Summary; Pattern 2 | Power-loss durability may be weaker on some filesystems. |
| A3 | A resumed process may use a new EventSink; persisted event position is enough to avoid sequence collisions. | Pitfall 4 | Event append coordination may need a durable event log contract. |
| A4 | Scenario factories can construct fresh Tool/Router instances and compare final state using explicit equality fields. | Pattern 5 | Stateful tools may require custom expected-state predicates. |

## Open Questions

1. **Should the checkpoint file include an in-progress Action separate from `RunState.recent_history`?**
   - What we know: D-01 asks for latest Action/ToolResult context, while D-02 writes only after a complete step [VERIFIED: 04-CONTEXT.md].
   - What's unclear: Whether to add `pending_action` metadata solely for diagnostics or rely on the previous checkpoint plus `duplicate_possible`.
   - Recommendation: Keep `pending_action` optional and diagnostic; do not treat it as execution authority. Resume from the last committed `RunState` and mark the injected crash window as possible duplicate [ASSUMED].
2. **How should event sequence metadata be represented?**
   - What we know: Existing `RuntimeEvent` has timestamp/run_id/step but no sequence field [VERIFIED: src/agentguard/events/model.py].
   - What's unclear: Add a monotonic `sequence` to `RuntimeEvent` or store a sink-local count in checkpoint metadata.
   - Recommendation: Add an optional sequence assigned by the sink/runtime and persist the next sequence; preserve existing JSONL fields for compatibility [ASSUMED].

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---:|---|---|
| Python runtime | Runtime/checkpoint implementation | ✓ | `python` 3.12.9 | — |
| `python3` command | Developer convenience | ✓ (wrong for project) | 3.9.6; project requires >=3.11 | Use `python`/conda interpreter [VERIFIED: `python3 --version`; pyproject.toml]. |
| pytest | Automated tests | ✓ | 8.3.5 | — |
| pytest-asyncio | Existing async tests | ✓ (tests currently collect under project environment) | version not queried | If absent, install dev dependency or run `asyncio.run` smoke scripts [ASSUMED]. |
| Redis/PostgreSQL/RabbitMQ | None (explicitly excluded) | Not required | — | Do not add services [VERIFIED: 04-CONTEXT.md]. |

**Missing dependencies with no fallback:** None for the locked local scope.  
**Missing dependencies with fallback:** `python3` 3.9 is below the project requirement; use the available Python 3.12 interpreter.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | no | Local single-user library; no auth boundary in Phase 4. |
| V3 Session Management | no | `run_id` is correlation metadata, not an authenticated session. |
| V4 Access Control | no | No multi-tenant or permission workflow in scope. |
| V5 Input Validation | yes | Strict JSON/schema/enum/path validation before resume; reject unknown versions and fields that violate invariants [VERIFIED: D-09]. |
| V6 Cryptography | no | No secrets or cryptographic material in checkpoint scope; do not invent encryption. |

### Known Threat Patterns for Python local file runtime

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Loading untrusted serialized objects | Tampering / Elevation | JSON only; never `pickle.loads` for checkpoints [CITED: https://docs.python.org/3/library/pickle.html]. |
| Path traversal or accidental overwrite | Tampering | Accept an explicit checkpoint path, create parent intentionally, and atomically replace only that target; no directory scanning [VERIFIED: D-04, D-08]. |
| Partial/truncated checkpoint | Denial of service | Same-directory temp file + flush/fsync + `os.replace`; preserve original on failure [CITED: https://docs.python.org/3/library/os.html#os.replace]. |
| Replay of non-idempotent side effects | Repudiation / Tampering | Document at-least-once semantics and emit `duplicate_possible`; exactly-once is out of scope [VERIFIED: D-03, D-10]. |

## Sources

### Primary (HIGH confidence)
- Existing AgentGuard source and tests (`src/agentguard/domain`, `runtime`, `events`, `tests`) — current contracts and integration points [VERIFIED: codebase grep].
- `.planning/phases/04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra/04-CONTEXT.md` — all locked Phase 4 decisions [VERIFIED: codebase read].
- Python standard library docs: `os.replace`, `json`, `tempfile`, `pathlib`, `pickle` [CITED: https://docs.python.org/3/library/os.html#os.replace; https://docs.python.org/3/library/json.html; https://docs.python.org/3/library/tempfile.html; https://docs.python.org/3/library/pathlib.html; https://docs.python.org/3/library/pickle.html].

### Secondary (MEDIUM confidence)
- None needed; no external framework or package is recommended for this local phase.

### Tertiary (LOW confidence)
- Filesystem power-loss durability and directory `fsync` behavior are intentionally not asserted; see Assumptions Log A2.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — project declares Python >=3.11 and current code uses only stdlib; no new packages [VERIFIED: pyproject.toml].
- Architecture: HIGH — integration points are explicit in locked context and existing Runtime loop [VERIFIED: 04-CONTEXT.md; engine.py].
- Pitfalls: MEDIUM — ordering/validation issues are derived from code and decisions; filesystem crash durability remains an assumption.

**Research date:** 2026-09-01  
**Valid until:** 2026-10-01 for stable stdlib APIs; revisit sooner if checkpoint schema or Runtime contracts change.
