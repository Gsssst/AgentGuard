# Phase 11: Event Contract and Collector - Research

**Researched:** 2026-09-06
**Domain:** Versioned runtime event contracts, safe telemetry projection, and process-local collection
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### 事件契约与验证
- **D-01:** envelope 的公共字段必须严格校验；每种已知 `event_type` 使用自己的 payload 字段约束，而不是继续接受任意字典。
- **D-02:** schema 标识固定为 `agentguard.event.v1`。v1 的既有含义不得静默改变；不兼容演进必须新增 v2。
- **D-03:** 所有 envelope 使用固定顶层结构。最终结构至少包含 `schema_version`、`run_id`、`sequence`、`occurred_at`、Collector 接收时间、`event_type`、`status`、`step`、`call_id`、`tool_call_id`、`batch_id`、`payload` 和 `extensions`；不适用的关联字段显式为 `null`。
- **D-04:** 未声明的扩展内容只能进入明确的 `extensions`，不得混入受约束的 payload 或顶层字段。
- **D-05:** 格式错误、未知 schema 或不支持的事件不得进入正常时间线。Collector 记录安全诊断或拒绝计数，但自身验证失败不能抛回并中断被观测的 Agent。

### 工具调用与批次关联
- **D-06:** AgentGuard 增加内部 `call_id` 作为逻辑工具调用的关联键；外部框架的 `tool_call_id` 原样保留、允许为 `null`，也不得被假定为唯一。
- **D-07:** 同一逻辑调用在初次执行、自动重试、审批恢复和 checkpoint 恢复时保持同一个 `call_id`。不同的实际执行通过 `attempt`、`resume_attempt` 和 `duplicate_possible` 等安全字段区分。
- **D-08:** 批量执行使用独立、可空的顶层 `batch_id`。批次开始/结束及批次内调用始终保留真实 `run_id` 并共享同一个 `batch_id`；不得再以 `batch_id` 冒充 `run_id`。
- **D-09:** 从 action 提议、审批、工具开始、每次尝试与重试到最终成功/失败/超时/取消，所有工具生命周期事件都必须携带同一 `call_id`。运行级事件的 `call_id` 为 `null`。
- **D-10:** 现有 Runtime 和 Adapter 由内部适配层自动生成并传播关联字段；使用者不需要为旧 `RuntimeEvent` 手工补充 `call_id`。

### 序号、重复与运行身份
- **D-11:** 顶层 `sequence` 只由 Collector 按 `run_id` 分配，是时间线排序和未来 SSE 重连的唯一权威序号。
- **D-12:** 来源侧已有的 `data.sequence` 不参与排序；如需保留，只能规范化为 `extensions.source_sequence` 供诊断。
- **D-13:** Collector 不进行内容哈希去重，也不按来源序号静默去重。每次实际接收的有效事件都分配新的 `sequence`；真实 replay 或重复副作用证据必须保留。
- **D-14:** 时间线按 Collector 接受顺序稳定排列。`occurred_at` 保留来源发生时间，另记 Collector 接收时间；迟到事件不得插回旧位置或重排已经建立的 sequence。
- **D-15:** 一个 `run_id` 永远表示一次逻辑运行。checkpoint 恢复通过 `resume_started` 继续原运行；进入 `completed`、`failed` 或 `cancelled` 终态后，后续普通事件拒绝进入时间线并产生安全诊断。新运行必须使用新 `run_id`。

### 安全 payload 与运行摘要
- **D-16:** 工具参数和返回值只保留递归脱敏后的有限预览。字符串、数组、对象都必须有长度和深度上限，发生裁剪时明确标记 `truncated: true`。
- **D-17:** v0.4 不提供关闭脱敏或展示原始值的开关；安全投影是 Collector 的固定边界，而不是 UI 选项。
- **D-18:** 失败事件只暴露允许列表中的稳定字段，例如 `error_type`、`failure_kind`、`attempts`、timeout 信息和 AgentGuard 生成的安全摘要。原始异常消息与 stack trace 永远不进入 envelope、后续 JSONL 或 SSE。
- **D-19:** 运行摘要使用 `running`、`waiting_approval`、`completed`、`failed`、`cancelled` 五态状态机。单个工具失败、超时或拒绝只是运行内事件，不能自行把整次运行改为失败；只有运行级终止事件能进入最终状态。
- **D-20:** `approval_requested` 可把运行置为 `waiting_approval`；批准或恢复执行后回到 `running`，最终状态一旦进入便不可回退。
- **D-21:** Collector 首先收到非 `run_started` 事件时仍创建临时摘要，记录 `first_observed_at` 并设置 `incomplete_start=true`。在有效 `run_started` 到达前，`started_at` 和 `duration` 必须为 `null`，不得伪造开始时间。

### the agent's Discretion
- Python 模型的具体组织方式（dataclass、枚举、校验辅助函数及模块命名），只要保持核心包轻量且不引入 Console Web 依赖。
- 各 `event_type` 的精确 payload allowlist、事件级 `status` 映射和安全摘要措辞，但必须覆盖 OBS-03/04 并遵守上述固定 envelope。
- `call_id` 与 `batch_id` 的具体生成算法及 checkpoint 传播方式，只要稳定、无碰撞风险、不会从敏感参数生成可推断标识，并满足恢复语义。
- 参数/结果预览的具体长度、集合大小、递归深度默认值及截断表示，只要默认有界、可测试且不可关闭脱敏。
- Collector 拒绝诊断的数据结构、错误计数名称，以及进程内运行索引的合理有界容量和淘汰细节；不得让诊断递归进入普通事件流或让内存无界增长。

### Deferred Ideas (OUT OF SCOPE)
- JSONL append/reload、截断尾行处理和历史恢复 — Phase 12。
- FastAPI run list/detail API 与内置运行启动入口 — Phase 12。
- SSE、`Last-Event-ID`、慢订阅者队列和外部 ingestion 幂等/传输重试 — Phase 13。
- React run list、timeline、event drawer 和浏览器测试 — Phase 14。
- 网页 approve/deny、认证、RBAC、多租户、分布式 event bus、OpenTelemetry 桥接和生产级 HA — v0.4 之后。
- 原始参数、原始返回值或原始异常的 Console 调试开关不会进入 v0.4。
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-03 | Every collected event uses a versioned envelope with `run_id`, monotonic per-run sequence, UTC timestamp, event type, status, and safe payload fields. | Fixed v1 dataclass contract, UTC normalization, per-event payload registry, and atomic per-run sequence allocation are specified below. [VERIFIED: `.planning/REQUIREMENTS.md`, `.planning/phases/11-event-contract-and-collector/11-CONTEXT.md`] |
| OBS-04 | The collector represents tool calls, approvals, failures, retries, timeouts, and terminal results without exposing raw exception stacks or secrets. | The event matrix, correlation propagation, bounded safe preview, fixed error-summary allowlist, and adapter emission gaps are specified below. [VERIFIED: `.planning/REQUIREMENTS.md`, codebase inspection] |
| COMPAT-01 | AgentGuard core remains importable and testable without installing the console's FastAPI or frontend dependencies. | The recommendation uses only Python's standard library in core and preserves the existing legacy `RuntimeEvent`/sink API. [VERIFIED: `pyproject.toml`, codebase inspection] |
</phase_requirements>

## Summary

Phase 11 should add a strict **second boundary** around the existing `RuntimeEvent`, not replace the v0.3 event model in place. `RuntimeEvent` and `EventSink.emit()` are already consumed by the CLI, reports, evaluation scenarios, and 136 tests; preserving that source contract while adding `normalize_runtime_event()` and `EventCollector` minimizes compatibility risk. [VERIFIED: `src/agentguard/events/model.py`, `src/agentguard/events/sinks.py`, repository `rg`, baseline `PYTHONPATH=src pytest -q`]

The current producer path is not yet sufficient for the new contract: source sequence is nested in `data`, batch events use `batch_id` as `run_id`, tool errors carry raw `error_message`, call correlation does not exist, and adapter-side validation/approval failures can return `ToolMessage` values without emitting Runtime events. These are producer defects that must be repaired before making the Collector strict; a normalizer must not infer correlation from event order or copy arbitrary legacy `data` into `extensions`. [VERIFIED: `src/agentguard/runtime/engine.py:777-812`, `src/agentguard/integrations/langgraph.py:172-295`]

Implement the work in three boundaries: (1) standard-library contract, safe projection, and strict normalizer; (2) Runtime/checkpoint/LangGraph propagation of `call_id`, `tool_call_id`, and `batch_id`; (3) a lock-protected, bounded Collector that atomically assigns per-run sequence numbers and advances an explicit summary state machine. [VERIFIED: Phase 11 D-01..D-21; architecture recommendation based on existing module seams]

**Primary recommendation:** Preserve `RuntimeEvent` as the internal source fact, add a strict `agentguard.event.v1` normalization layer, and allow only the Collector to construct sequenced public envelopes. [VERIFIED: Phase 11 D-02, D-10..D-12]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Emit source execution facts and correlation IDs | Runtime / LangGraph adapter | Checkpoint codec | The producer knows logical call and batch identity; the Collector cannot reconstruct it safely from ordering. [VERIFIED: codebase inspection, Phase 11 D-06..D-10] |
| Validate and project `agentguard.event.v1` | Core events package | Shared safety helper | This boundary must remain independent of FastAPI and frontend packages. [VERIFIED: COMPAT-01, Phase 11 D-01..D-05] |
| Assign sequence and update summaries | Process-local EventCollector | Bounded diagnostics index | Sequence and state transition must commit atomically for each accepted event. [VERIFIED: Phase 11 D-11..D-15, D-19..D-21] |
| Persist JSONL and reload history | Future backend/storage tier | EventCollector | Explicitly deferred to Phase 12. [VERIFIED: Phase 11 Deferred Ideas] |
| Expose REST/SSE/UI | Future API/browser tiers | EventCollector | Explicitly deferred to Phases 12-14. [VERIFIED: `.planning/ROADMAP.md`] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python standard library | `>=3.11` | `dataclasses`, `enum.StrEnum`, `datetime`, `threading`, `collections`, `uuid`, `json` | The package already requires Python 3.11 and uses dataclasses/StrEnum for public contracts; no new dependency is needed. [VERIFIED: `pyproject.toml`, codebase inspection] |
| `dataclasses` | Python 3.11+ | Frozen envelope/summary/diagnostic values and `__post_init__` validation | The generated initializer calls `__post_init__`, and frozen dataclasses emulate read-only instances. [CITED: https://docs.python.org/3.11/library/dataclasses.html] |
| `datetime` | Python 3.11+ | Parse source ISO timestamps, reject naive values, normalize to UTC | Python 3.11 `datetime.fromisoformat()` accepts `Z`, and `datetime.UTC` aliases the UTC singleton. [CITED: https://docs.python.org/3.11/library/datetime.html] |
| `threading.Lock` | Python 3.11+ | Protect sequence allocation plus run-index mutation across tasks and OS threads | `asyncio` locks are not thread-safe; primitive thread locks provide mutual exclusion and context-manager support. [CITED: https://docs.python.org/3.11/library/asyncio-sync.html, https://docs.python.org/3.11/library/threading.html] |
| `collections.deque(maxlen=...)` | Python 3.11+ | Bounded retained events and diagnostics | A bounded deque discards from the opposite end when full, making retention explicit and memory-bounded. [CITED: https://docs.python.org/3.11/library/collections.html#collections.deque] |
| `uuid` | Python 3.11+ | Opaque call and batch identifiers without using arguments or exception text | `uuid4()` creates random UUIDs; name-based UUIDs are available when deterministic recovery coordinates are required. [CITED: https://docs.python.org/3.11/library/uuid.html] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.3.5 locally; project range `>=8,<10` | Contract, state-machine, concurrency, and deliberate-failure tests | Existing project test framework; run with `PYTHONPATH=src pytest -q`. [VERIFIED: local environment, `pyproject.toml`] |
| pytest-asyncio | 0.24.0 locally; project range `>=0.24,<2` | Runtime and adapter integration tests | Existing async test support only; Collector unit tests should remain synchronous where possible. [VERIFIED: local environment, `pyproject.toml`] |
| LangGraph / langchain-core | 0.6.11 / 0.3.86 | Verify adapter correlation across prepare/approval/resume | Existing optional extra; it must not become a core import requirement. [VERIFIED: local package metadata, `pyproject.toml`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Standard-library contract validation | Pydantic | Pydantic would reduce some validation code, but it would add a runtime dependency to the core for a closed, small schema and conflicts with the locked lightweight boundary. [VERIFIED: COMPAT-01 and Phase 11 discretion] |
| Synchronous `threading.Lock` | `asyncio.Lock` | `EventSink.emit()` is synchronous and may be called from OS threads; Python documents asyncio synchronization primitives as not thread-safe. [CITED: https://docs.python.org/3.11/library/asyncio-sync.html] |
| Source-generated sequence | Collector-generated sequence | Source positions reset or resume and current batch/runtime paths share one mutable `_event_sequence`; only Collector allocation satisfies D-11. [VERIFIED: `src/agentguard/runtime/engine.py:49,79-81,277-280,777-812`] |

**Installation:** No package installation is required for Phase 11 core implementation. [VERIFIED: selected standard-library design and COMPAT-01]

## Package Legitimacy Audit

No external package is introduced in this phase, so registry and slopcheck verification are not applicable. [VERIFIED: Standard Stack recommendation]

## Architecture Patterns

### System Architecture Diagram

```text
Runtime.run / Runtime.execute_* / GuardedToolNode
                    |
                    | RuntimeEvent + explicit correlation context
                    v
        strict RuntimeEvent normalizer
          | schema/payload valid? |
          | yes                   | no
          v                       v
      safe normalized fact   bounded diagnostic counter/deque
          |                       |
          |                 never re-enters event flow
          v
 EventCollector.accept transaction (threading.Lock)
          |
          +--> assign received_at + next per-run sequence
          +--> append to bounded per-run timeline
          +--> advance immutable RunSummary snapshot
          |
          v
 agentguard.event.v1 EventEnvelope
          |
          +--> Phase 12 JSONL / REST
          +--> Phase 13 SSE / ingestion
          +--> Phase 14 React timeline
```

The adapter and Runtime are the only reliable places to create correlation identifiers because they know whether an event belongs to a logical call, retry, approval resume, or batch member. The Collector should validate correlation but never infer it from adjacent events. [VERIFIED: Phase 11 D-06..D-10 and current producer code]

### Component Responsibilities

| Component | Responsibility | Must Not Do |
|-----------|----------------|-------------|
| Legacy `RuntimeEvent` | Continue carrying source facts to existing sinks and reports. [VERIFIED: current codebase] | Become the persisted/streamed v1 envelope or change its existing `to_dict()` shape in Phase 11. [VERIFIED: compatibility requirement and current consumers] |
| Correlation context/factory | Create and validate `call_id`, `tool_call_id`, and `batch_id`; pass them through every producer branch. [VERIFIED: Phase 11 D-06..D-10] | Hash raw arguments or exception messages into public identifiers. [VERIFIED: Phase 11 discretion] |
| Safe preview helper | Recursively copy JSON-safe values, redact sensitive keys/patterns, enforce depth/item/node/string bounds, and report truncation. [VERIFIED: Phase 11 D-16..D-18] | Call arbitrary user `repr()`/`str()` or retain a reference to caller-owned containers. [VERIFIED: security analysis of tool-owned values] |
| RuntimeEvent normalizer | Map each known `EventType` through an exact payload spec and deterministic event-status mapping. [VERIFIED: Phase 11 D-01..D-04] | Copy unknown legacy keys into payload/extensions or include raw `error_message`, checkpoint paths, loop signatures, or stacks. [VERIFIED: current sensitive fields and Phase 11 D-04/D-18] |
| EventCollector | Catch normalization failures, allocate sequence atomically, retain bounded events/diagnostics, and update summaries. [VERIFIED: Phase 11 D-05, D-11..D-15, D-19..D-21] | Raise a collection failure back through `EventSink.emit()` or invoke callbacks while holding its state lock. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html] |

### Recommended Project Structure

```text
src/agentguard/
├── _safety.py                 # shared redact + bounded safe-preview semantics
├── events/
│   ├── model.py               # existing EventType/RuntimeEvent, compatibility preserved
│   ├── contract.py            # EventEnvelope, statuses, payload specs, validation errors
│   ├── normalize.py           # RuntimeEvent -> safe unsequenced fact
│   ├── collector.py           # EventCollector, RunSummary, diagnostics, bounded index
│   ├── sinks.py               # existing sink Protocol and legacy sinks
│   └── __init__.py            # dependency-light exports
├── runtime/
│   ├── engine.py              # producer correlation and real run/batch IDs
│   └── permission.py          # retains public redact API by delegating to _safety
├── checkpoint/
│   ├── model.py               # optional persisted pending call correlation
│   └── codec.py               # backward-compatible optional field codec
└── integrations/
    ├── langgraph.py           # per-input internal call IDs + adapter event emission
    └── approval.py            # carries correlation through prepared state/resume

tests/
├── unit/
│   ├── test_event_contract.py
│   ├── test_event_safety.py
│   └── test_event_collector.py
└── integration/
    ├── test_event_correlation.py
    └── test_langgraph_observability.py
```

This split keeps the new public contract independent of `runtime.engine` and optional integrations; moving shared redaction downward also avoids creating an `events -> runtime.permission -> runtime package -> engine -> events` import cycle. [VERIFIED: current package import graph in `src/agentguard/__init__.py`, `src/agentguard/runtime/__init__.py`, and `src/agentguard/events/__init__.py`]

### Pattern 1: Strict Envelope, Declarative Payload Specs

**What:** Use a frozen, keyword-only `EventEnvelope` dataclass for the fixed top level and an internal `PayloadSpec` registry keyed by every `EventType`. Each spec declares required/optional fields, field validators, and the one allowed event-level status mapping. Unknown payload fields fail validation; explicitly supported diagnostic metadata goes to a separately validated `extensions` mapping. [VERIFIED: Phase 11 D-01..D-04; Python dataclass behavior cited below]

**Why this shape:** Twenty-three event types currently share the same external dictionary shape but emit different `data` keys. A small declarative registry avoids twenty-three mostly boilerplate payload classes while still providing per-event exactness. [VERIFIED: `src/agentguard/events/model.py` and Runtime emit sites]

**Recommended fixed fields:**

```python
@dataclass(frozen=True, kw_only=True)
class EventEnvelope:
    schema_version: str
    run_id: str
    sequence: int
    occurred_at: str
    received_at: str
    event_type: EventType
    status: EventStatus
    step: int | None
    call_id: str | None
    tool_call_id: str | None
    batch_id: str | None
    payload: Mapping[str, JsonValue]
    extensions: Mapping[str, JsonValue]
```

Dataclass annotations are not runtime type enforcement, so `__post_init__` must reject `bool` where an integer is required, reject empty/overlong IDs, require `sequence >= 1`, require UTC-aware timestamps, enforce tool-event correlation, and deep-copy/freeze nested payload values. [CITED: https://docs.python.org/3.11/library/dataclasses.html; VERIFIED: existing project validation style]

### Pattern 2: Explicit Event Status Mapping

The top-level event `status` should describe the event outcome, not mutate the run summary directly. Use the closed vocabulary `running`, `waiting`, `succeeded`, `failed`, `timed_out`, `cancelled`, and `completed`; then map event types deterministically. [VERIFIED: Phase 11 D-01/D-19; recommended mapping]

| Event group | Event status | Run-summary effect |
|-------------|--------------|--------------------|
| `run_started`, `action_proposed`, `tool_started`, `tool_attempt_started`, `checkpoint_written`, `resume_started`, `duplicate_possible`, `batch_started` | `running` | Create/retain `running`; `resume_started` returns `waiting_approval` to `running`. [VERIFIED: D-19/D-20] |
| `retry_scheduled`, `resource_waiting` | `waiting` | No terminal change. [VERIFIED: D-19] |
| `approval_requested` | `waiting` | Set `waiting_approval`. [VERIFIED: D-20] |
| `approval_granted`, `tool_succeeded` | `succeeded` | Approval grant returns to `running`; tool success does not end the run. [VERIFIED: D-19/D-20] |
| `tool_failed`, `permission_denied`, `approval_denied`, `loop_detected`, `recovery_rejected` | `failed` | Do not enter a run terminal state. [VERIFIED: D-19] |
| `tool_timed_out`, `resource_lock_timeout` | `timed_out` | Do not enter a run terminal state. [VERIFIED: D-19] |
| `tool_cancelled` | `cancelled` | Do not mark the run cancelled without `run_finished`. [VERIFIED: D-19] |
| `batch_finished` | `completed` | Batch completion is not run completion, even when `failed > 0`. [VERIFIED: current batch semantics and D-19] |
| `run_finished` | payload-derived `completed` / `failed` / `cancelled` | The only transition into a terminal run state. [VERIFIED: D-15/D-19] |

### Pattern 3: Payload Allowlists, Not Legacy Data Passthrough

The normalizer should explicitly consume the legacy keys below. Common source metadata (`sequence`, `resume_attempt`, `duplicate_possible`) is handled separately; only `sequence` becomes `extensions.source_sequence`. Any other unexpected legacy key is a rejected contract violation rather than an automatic extension. [VERIFIED: Phase 11 D-04/D-12]

| Event type | Required safe payload | Optional safe payload / transformation |
|------------|-----------------------|----------------------------------------|
| `run_started` | none | `resume_attempt`, `duplicate_possible`. [VERIFIED: current `_emit()` defaults] |
| `action_proposed` | `action_type` | Tool branch: bounded `tool_name` and `arguments` preview; finish branch: omit raw free-text reason or replace it with a fixed presence flag. [VERIFIED: current emit data; D-16/D-18] |
| `tool_started` | `tool_name` | `resume_attempt`, `duplicate_possible`. [VERIFIED: current emit data] |
| `tool_attempt_started` | `tool_name`, `attempt`, `max_attempts`, `retry_safety` | `timeout_seconds`, `timeout_source`. [VERIFIED: `src/agentguard/runtime/tool.py:176-188`] |
| `retry_scheduled` | `tool_name`, `completed_attempt`, `next_attempt`, `max_attempts`, `delay_seconds` | `failure_kind`. [VERIFIED: `src/agentguard/runtime/tool.py:226-240`] |
| `tool_succeeded` | `tool_name`, `attempts`, bounded `result` preview | Never pass source `value` directly. [VERIFIED: current emit data; D-16] |
| `tool_failed` | `tool_name`, `error_type`, `failure_kind`, `attempts`, fixed `safe_summary` | Explicitly drop source `error_message`. [VERIFIED: current raw error path; D-18] |
| `tool_timed_out` | `tool_name`, `attempts`, `timeout_seconds`, `timeout_source`, fixed `safe_summary` | none. [VERIFIED: current emit data; D-18] |
| `tool_cancelled` | `tool_name`, `attempts`, fixed `safe_summary` | none. [VERIFIED: current emit data; D-18] |
| `loop_detected` | `consecutive_count`, `threshold` | Replace raw action signature with no value or a non-reversible, explicitly labeled diagnostic digest; the current signature contains canonical arguments. [VERIFIED: `src/agentguard/runtime/loop_guard.py`] |
| `checkpoint_written` | `lifecycle` | Do not expose `checkpoint_path`. [VERIFIED: current emit data; OWASP identifies file paths as potentially sensitive] |
| `resume_started` | `resume_attempt`, `duplicate_possible` | Do not expose `checkpoint_path`. [VERIFIED: current emit data; D-18] |
| `duplicate_possible` | `resume_attempt` | fixed `safe_summary`. [VERIFIED: existing EventType vocabulary] |
| `recovery_rejected` | `error_type`, fixed `safe_summary` | no raw error/path. [VERIFIED: existing EventType vocabulary; D-18] |
| `permission_denied` | `tool_name`, capabilities, `decision` | fixed `safe_summary`. [VERIFIED: current emit data] |
| `approval_requested` | `tool_name`, capabilities, `decision`, exact-format `action_digest`, arguments preview | Event top-level correlation remains authoritative. [VERIFIED: current emit data; D-09/D-16] |
| `approval_granted`, `approval_denied` | `tool_name`, capabilities, bounded actor label, exact-format `action_digest`, fixed `safe_summary` | Do not copy arbitrary source reason. [VERIFIED: current emit data; D-18] |
| `resource_waiting` | `tool_name`, bounded resource IDs | Do not expose lock/thread ownership. [VERIFIED: Phase 8/11 context] |
| `resource_lock_timeout` | `tool_name`, bounded resource IDs, `failure_kind`, fixed `safe_summary` | Explicitly drop source `error_message`. [VERIFIED: current emit data; D-18] |
| `batch_started` | `size` | none. [VERIFIED: current emit data] |
| `batch_finished` | `size`, `failed` | Validate `0 <= failed <= size`. [VERIFIED: current emit data] |
| `run_finished` | run terminal `status`, `stop_reason` | Terminal status is restricted to `completed`, `failed`, `cancelled`. [VERIFIED: D-15/D-19] |

### Pattern 4: Source-Owned Correlation Context

Introduce one immutable correlation value (`call_id`, nullable `tool_call_id`, nullable `batch_id`) and pass it into `_emit`, `_emit_external`, `execute_explicit_tool`, and `execute_explicit_batch`. ToolExecutor callbacks close over the same context, so attempts and retries cannot accidentally receive a new ID. [VERIFIED: current callback seam at `engine.py:184-187,485-489`; Phase 11 D-06..D-10]

For sequential Runtime calls, derive `call_id` from a stable, non-secret logical coordinate such as a namespaced UUID over `run_id + step`; this keeps the same ID when a pre-checkpoint tool action is replayed after a crash without hashing arguments. For batch calls, create `batch_id` once and derive or allocate one distinct `call_id` per input index, then store those IDs in LangGraph `_agentguard_prepared` and approval checkpoint state. [CITED: https://docs.python.org/3.11/library/uuid.html; VERIFIED: existing checkpoint and prepared-state seams; recommended design]

Do not equate `tool_call_id` with `call_id`: the adapter currently accepts invalid IDs via local placeholders and handles duplicate external IDs independently; source evidence is not a safe unique key. [VERIFIED: `src/agentguard/integrations/langgraph.py:172-215`, Phase 11 D-06]

### Pattern 5: Logical Batch Lifecycle Owned at the Adapter Boundary

`execute_explicit_batch()` currently emits batch events with `run_id` passed as the `batch_id` argument, while `execute_batch()` emits `batch_id` as the event's `run_id`. Both paths must accept real `run_id` and separate `batch_id`. [VERIFIED: `src/agentguard/runtime/engine.py:527-551,634-682,793-803`]

A mixed LangGraph batch is split into direct and approval-pending subsets. Generate the logical `batch_id` before partitioning, pass it to direct execution, persist it with pending calls, reuse it after resume, and emit only one logical `batch_started`/`batch_finished` pair for the original AIMessage. A Runtime option to suppress subset-level batch lifecycle events is preferable to emitting misleading duplicate batch boundaries. [VERIFIED: `src/agentguard/integrations/langgraph.py:181-295,358-387`; recommended design]

Adapter-side early failures and approval requests currently bypass Runtime execution and therefore may not emit any `RuntimeEvent`. Add a small Runtime-owned framework-event emission seam (or equivalent internal producer helper) so invalid/unknown/unguarded calls, `approval_requested`, missing/denied approvals, and digest mismatches enter the same sink with safe payloads and full correlation. [VERIFIED: `src/agentguard/integrations/langgraph.py:181-239,251-295,325-351`]

### Pattern 6: Atomic Collector Transaction

Normalize and safe-copy the untrusted source event before acquiring the state lock. Then, under one `threading.Lock`, check terminal-run constraints, allocate `next_sequence = last_sequence + 1`, construct the final envelope with a precomputed `received_at`, append it, and update the summary. Do not call clocks, normalizers, user callbacks, downstream sinks, or diagnostic formatting while holding the lock. [CITED: https://docs.python.org/3.11/library/threading.html; recommended deadlock-avoidance design]

Expose snapshots (`tuple[EventEnvelope, ...]`, frozen `RunSummary`) rather than internal mutable lists/dicts. `EventCollector.emit()` should preserve the existing `None`-returning sink Protocol; a separate `accept()` may return a typed `CollectionResult` for tests and future ingestion, but neither path may raise validation or internal collector exceptions into the observed Agent. [VERIFIED: `src/agentguard/events/sinks.py`; Phase 11 D-05]

### Pattern 7: Bounded Safe Preview

Use one shared projector below both the existing public `redact()` API and new event normalization. Traverse only mappings, lists/tuples, and JSON primitives; track visited container identities; reject or replace cycles and unsupported types without calling arbitrary `repr()`/`str()`; normalize non-finite floats; redact sensitive key markers before traversing their values; and enforce depth, per-collection item, string, and total-node budgets. [VERIFIED: current `redact()` only bounds neither shape nor cycles; D-16..D-18; JSON strictness cited below]

Recommended initial limits are depth 4, 20 items per collection, 512 characters per string, and 200 total visited nodes. Return a stable wrapper such as `{"value": ..., "truncated": true|false}` for every argument/result preview so truncation is never inferred from a magic string. These tuning values are conservative project defaults, not performance guarantees. [ASSUMED]

Before accepting the projection, `json.dumps(projected, allow_nan=False)` should succeed; Python otherwise permits JavaScript spellings for NaN and infinities by default. [CITED: https://docs.python.org/3.11/library/json.html]

### Pattern 8: Explicit Run-Summary State Machine

Use a frozen `RunSummary` snapshot with at least `run_id`, `status`, `first_observed_at`, nullable `started_at`, nullable `finished_at`, nullable `duration_seconds`, `event_count`, `retained_event_count`, `last_sequence`, and `incomplete_start`. [VERIFIED: OBS-03 and Phase 11 D-19..D-21]

State transitions should be a table, not scattered conditionals:

```text
missing --any valid event--> running + incomplete_start=true
missing --run_started-----> running + started_at + incomplete_start=false
running --approval_requested--> waiting_approval
waiting_approval --approval_granted/resume_started/tool_started--> running
running|waiting_approval --run_finished(completed|failed|cancelled)--> terminal
terminal --any later event--> reject + bounded diagnostic
```

A later `run_started` may backfill a non-terminal incomplete summary without rewriting earlier sequences; a repeated `run_started` for an already started non-terminal run must not reset `started_at` or counters. [VERIFIED: D-14/D-15/D-21; recommended edge behavior]

Compute duration only when both a valid start and terminal timestamp exist and the result is non-negative; otherwise keep duration `null` and add a safe diagnostic. This avoids inventing duration for late/missing starts or clock regressions. [VERIFIED: D-21 and milestone clock pitfall; recommended behavior]

### Pattern 9: Bounded Index and Diagnostics

Keep a bounded deque of events per run and a bounded deque of `CollectorDiagnostic` values. Track total `event_count`, retained count, and earliest retained sequence separately so silent deque eviction never looks like a complete history. [CITED: https://docs.python.org/3.11/library/collections.html#collections.deque; VERIFIED: Phase 11 discretion]

Use a bounded run index. Evict the oldest terminal run first; if all retained runs are active/waiting and the index is full, reject creation of another run with a safe capacity diagnostic rather than evicting live state. Exact capacity defaults are configuration constants and must be tested with very small injected limits. [VERIFIED: Phase 11 discretion; recommended policy]

Diagnostics must contain only a code, receive time, safe source type/run label where available, and stable error category. Never include `str(exc)`, raw candidate payloads, or recursively emit diagnostics through `EventCollector.emit()`. [VERIFIED: D-05/D-18]

### Anti-Patterns to Avoid

- **Replacing `RuntimeEvent` outright:** It would break CLI JSONL, reports, and current tests before Phase 12 provides the new persistence path. Add normalization beside it. [VERIFIED: repository consumer scan]
- **Treating `extensions` as an unknown-field bucket:** This defeats strict payload evolution and can smuggle raw errors/secrets into future JSONL/SSE. Only explicitly named extension keys are accepted. [VERIFIED: D-04/D-18]
- **Inferring call IDs in Collector:** Concurrent batch completion and retries make adjacency ambiguous. Generate at the source and validate at collection. [VERIFIED: D-06..D-10 and concurrent batch architecture]
- **Using `_event_sequence` as v1 order:** It is Runtime-instance state, is restored from checkpoint positions, and currently mixes batch paths. Collector sequence must be independent. [VERIFIED: `engine.py:49,79-81,277-280,777-812`]
- **Holding a collector lock while invoking user-controlled code:** A custom clock, `repr`, callback, or sink can re-enter or block and create deadlocks. Precompute outside the critical section and publish only snapshots. [CITED: https://docs.python.org/3.11/library/threading.html; recommended mitigation]
- **Catching `BaseException`:** Collector fail-open behavior should catch validation/internal `Exception`, not suppress process control exceptions such as `KeyboardInterrupt` or `SystemExit`. [CITED: https://docs.python.org/3.11/library/exceptions.html#BaseException]
- **Copying `error_message`, checkpoint paths, loop signatures, approval reasons, or arbitrary objects:** All are current channels for secrets, local paths, raw arguments, or side-effectful string conversion. Use fixed summaries and bounded projections. [VERIFIED: codebase inspection; OWASP Logging Cheat Sheet]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UTC timestamp parsing | Regex-only ISO parser | `datetime.fromisoformat()` plus an explicit aware/UTC check and UTC normalization | Python 3.11 supports `Z` and timezone offsets; semantic timezone validation still belongs in the contract. [CITED: https://docs.python.org/3.11/library/datetime.html] |
| Identifier entropy/format | Ad-hoc random strings or argument hashes | `uuid4()` for new opaque identities and namespaced `uuid5()` only for explicit non-secret recovery coordinates | The standard library implements the UUID algorithms, and `uuid4()` avoids the privacy issue called out for address-based UUID1. [CITED: https://docs.python.org/3.11/library/uuid.html] |
| Cross-thread collection lock | A boolean flag or event-loop-only lock | `threading.Lock` around the minimal state transaction | Python explicitly documents asyncio primitives as not thread-safe. [CITED: https://docs.python.org/3.11/library/asyncio-sync.html] |
| Event-specific validation | Scattered `if event_type == ...` checks in producers, collector, JSONL, API, and UI | One payload-spec registry consumed by the normalizer and envelope decoder | A single contract prevents later Phase 12/13 consumers from inventing divergent schemas. [VERIFIED: D-01/D-02 and roadmap dependency order] |
| Secret/error sanitization | Passing `str(exc)`, regexing a serialized blob, or trusting UI masking | Source-independent fixed safe summaries plus the shared bounded structural projector | OWASP recommends excluding/masking tokens, passwords, keys and validating/sanitizing collected event data; logging failures should not stop the application. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html] |
| Bounded retention | Manual list trimming after every append | `deque(maxlen=...)` plus explicit dropped/retained sequence accounting | The standard bounded deque behavior is defined by Python; explicit accounting prevents silent completeness claims. [CITED: https://docs.python.org/3.11/library/collections.html#collections.deque] |

**Key insight:** The custom work in Phase 11 is AgentGuard's domain mapping—event vocabulary, correlation, safe payloads, and summary transitions. Standard-library primitives should own parsing, locking, IDs, and bounded containers. [VERIFIED: phase boundary and selected stack]

## Common Pitfalls

### Pitfall 1: Building the Strict Collector Before Repairing Producers

**What goes wrong:** Almost every current tool lifecycle event lacks `call_id`, and current batch events do not have separate run/batch identity, so a correct strict Collector would reject them. [VERIFIED: `src/agentguard/runtime/engine.py`]

**Why it happens:** The v0.3 event format was designed for local evidence, not cross-framework correlation. [VERIFIED: archived milestone implementation and Phase 11 context]

**How to avoid:** Plan producer correlation and adapter emission as a prerequisite or same wave as strict normalization; add integration tests that feed real Runtime/GuardedToolNode emissions into EventCollector. [VERIFIED: D-06..D-10]

**Warning signs:** Unit-created envelopes pass while a real retry, approval resume, or batch run increments `rejected_count`. [VERIFIED: expected failure mode from strict correlation]

### Pitfall 2: Confusing Event Status with Run Status

**What goes wrong:** A `tool_failed`, timeout, permission denial, or failed batch prematurely marks the entire run failed. [VERIFIED: risk prohibited by D-19]

**Why it happens:** Both concepts use words such as `failed` but have different lifecycles. [VERIFIED: current `ToolResultStatus` and `RunStatus` models]

**How to avoid:** Keep `EventStatus` and `RunSummaryStatus` as separate enums and transition the run to a terminal state only from `run_finished`. [VERIFIED: D-19]

**Warning signs:** The run summary is terminal before the final event, or a later successful retry is rejected as a post-terminal event. [VERIFIED: state-machine consequence]

### Pitfall 3: Shallow Redaction with Unbounded Traversal

**What goes wrong:** Nested secrets, huge collections, cycles, non-finite floats, or arbitrary objects either leak, consume excessive memory, fail JSON encoding, or invoke attacker-controlled string methods. [VERIFIED: current `redact()` implementation and JSON behavior]

**Why it happens:** Key-name masking alone is not a complete safe serialization boundary. [VERIFIED: `src/agentguard/runtime/permission.py:249-271`; OWASP exclusion guidance]

**How to avoid:** Apply key redaction before traversal, cap total nodes as well as depth/item/string sizes, detect cycles, avoid arbitrary coercion, and validate strict JSON serializability. [CITED: https://docs.python.org/3.11/library/json.html; VERIFIED: D-16]

**Warning signs:** Tests only cover `password` at one level, or `json.dumps()` is first called in Phase 12 rather than at normalization. [VERIFIED: current test coverage and future pipeline]

### Pitfall 4: Hiding Schema Drift in `extensions`

**What goes wrong:** A misspelled required field or newly introduced producer field appears in `extensions`, so v1 consumers silently receive incomplete or unsafe meaning. [VERIFIED: D-01/D-04 risk]

**Why it happens:** Automatically moving all unknown keys feels backward-compatible but removes the strict boundary. [VERIFIED: contract analysis]

**How to avoid:** Only accept named v1 extension keys; reject everything else and require an intentional contract change. [VERIFIED: D-04]

**Warning signs:** Normalization uses `extensions.update(unconsumed_data)`. [VERIFIED: anti-pattern derived from D-04]

### Pitfall 5: Sequence Allocation Outside the Lock

**What goes wrong:** Concurrent emitters receive duplicate or out-of-order per-run sequences, or summary counters disagree with retained events. [VERIFIED: concurrency invariant from D-11]

**Why it happens:** Increment, append, and summary update are treated as separate operations. [VERIFIED: state transaction analysis]

**How to avoid:** Commit terminal check, increment, envelope construction, append, and summary replacement under one lock; test with `ThreadPoolExecutor` and a barrier. [CITED: https://docs.python.org/3.11/library/threading.html; recommended test]

**Warning signs:** A test can observe `last_sequence != event_count` when no retention occurred. [VERIFIED: invariant]

### Pitfall 6: Re-entrant Diagnostics or Callbacks Under Lock

**What goes wrong:** A validation failure emits a diagnostic through the same Collector, or a subscriber callback re-enters it, causing recursion or deadlock. [VERIFIED: D-05 and prior user concern about deadlocks]

**Why it happens:** Diagnostics and publication are modeled as ordinary events. [VERIFIED: architecture risk]

**How to avoid:** Diagnostics use a private bounded deque/counters; no external callback is invoked while holding the lock. Phase 13 publication consumes accepted snapshots later. [VERIFIED: D-05 and deferred SSE scope]

**Warning signs:** `emit()` appears anywhere inside diagnostic handling or the locked critical section. [VERIFIED: architectural invariant]

### Pitfall 7: Losing Correlation Across Approval or Crash Resume

**What goes wrong:** A resumed attempt appears as a new tool call, making retry/replay evidence impossible to group. [VERIFIED: D-07]

**Why it happens:** `call_id` is generated inside each invocation rather than stored/derived at the logical-call boundary. [VERIFIED: correlation analysis]

**How to avoid:** Generate once; close over it for retries; persist it in pending approval/checkpoint state; for pre-checkpoint crash replay use a deterministic non-secret run/step coordinate or persist pre-execution correlation. [VERIFIED: current checkpoint seam; recommended design]

**Warning signs:** The same action's `approval_requested`, `approval_granted`, and `tool_started` events have different IDs. [VERIFIED: D-09]

### Pitfall 8: Breaking v0.3 Reports and CLI While Introducing v1

**What goes wrong:** Existing JSONL fixtures and `ReliabilityReport` stop understanding events before Phase 12 migrates them. [VERIFIED: current consumers]

**Why it happens:** The public envelope is mistakenly implemented by changing `RuntimeEvent.to_dict()`. [VERIFIED: compatibility risk]

**How to avoid:** Preserve the legacy model/sinks, add v1 types beside them, and run the full 136-test suite after each integration task. [VERIFIED: baseline suite and COMPAT-01]

**Warning signs:** `test_event_sinks.py` or `test_report.py` requires wholesale fixture rewrites unrelated to call correlation. [VERIFIED: current test shape]

## Deterministic Test and Failure Matrix

Nyquist validation is explicitly disabled in `.planning/config.json`, so this research does not add the formal `Validation Architecture` section. The phase still requires focused automated and deliberate-failure tests because the project mandates evidence for each reliability feature. [VERIFIED: `.planning/config.json`, `.planning/PROJECT.md`]

| Area | Required deterministic test | Deliberate failure being proved |
|------|-----------------------------|--------------------------------|
| Envelope | Table-driven valid example for every `EventType`; reject wrong schema, missing/extra fields, bool-as-int, empty IDs, invalid/naive/non-UTC timestamp, wrong correlation nullability. [VERIFIED: D-01..D-04] | Invalid data never reaches normal timeline. [VERIFIED: D-05] |
| Safe preview | Nested markers, long strings, wide/deep structures, cycles, NaN/Infinity, bytes, unsupported objects, caller mutation after collection. [VERIFIED: D-16..D-18; JSON docs] | Projection is bounded, JSON-strict, and does not leak known secrets. [VERIFIED: OBS-04] |
| Error safety | Exceptions whose message contains token, filesystem path, newline, and arguments; assert none appears in envelope or diagnostics. [VERIFIED: D-18; current raw error paths] | Raw exception message/stack cannot cross the v1 boundary. [VERIFIED: D-18] |
| Collector sequencing | Concurrent threads emit N events for one run and interleave a second run; assert each run receives exactly `1..N` in Collector acceptance order with no duplicates. [VERIFIED: D-11/D-14] | Allocation remains atomic across OS threads. [CITED: Python threading docs] |
| Duplicate/late events | Submit identical events twice and timestamps in reverse order; assert both retained and sequence remains receive-ordered. [VERIFIED: D-13/D-14] | No content/source-sequence dedupe and no historical reorder. [VERIFIED: D-13/D-14] |
| State machine | Missing start, late valid start, approval wait/grant, tool failure then success, terminal transition, post-terminal event. [VERIFIED: D-15/D-19..D-21] | Only run terminal events terminate; post-terminal reuse rejects safely. [VERIFIED: D-15/D-19] |
| Retention | Instantiate limits of 2 runs/3 events/2 diagnostics and exceed each. [VERIFIED: bounded-index requirement] | Memory stays bounded and truncation/eviction is observable. [VERIFIED: Phase 11 discretion] |
| Sink isolation | Feed malformed event and inject a normalizer/internal `Exception`; assert `emit()` returns and a surrounding Runtime completes. [VERIFIED: D-05] | Collector failure cannot break the observed Agent. [CITED: OWASP Logging Cheat Sheet] |
| Sequential correlation | Success, transient retry, timeout, approval pause/resume, and crash/checkpoint resume; assert one `call_id` per logical call and attempts/resume flags distinguish executions. [VERIFIED: D-07/D-09] | Correlation survives every lifecycle boundary. [VERIFIED: D-07] |
| Batch correlation | Multiple calls with distinct/duplicate/invalid external IDs; assert unique internal IDs, one shared batch ID, real run ID, and input-order-independent completion. [VERIFIED: D-06/D-08; Phase 8 decisions] | External ID cannot become the internal primary key. [VERIFIED: D-06] |
| Adapter gaps | Unknown tool, missing guard, approval pending, missing decision, denial, digest mismatch, and approved failure all create correlated safe events. [VERIFIED: current adapter early-return branches] | ToolMessage-only failure paths no longer disappear from observability. [VERIFIED: OBS-04] |
| Compatibility | `PYTHONPATH=src python -c "import agentguard"`, full core suite without Console extras, and existing LangGraph optional tests. [VERIFIED: COMPAT-01] | New core exports do not pull FastAPI/frontend/LangGraph unconditionally. [VERIFIED: COMPAT-01] |

Inject `clock`, `id_factory`, and small retention limits into Collector/producer helpers. Tests can then assert exact timestamps/IDs without sleeping, and concurrency tests only assert invariants rather than unstable thread acquisition order. [VERIFIED: deterministic project constraint; recommended design]

## Code Examples

Verified implementation patterns from Python's standard library and the existing AgentGuard style follow.

### UTC Normalization and Strict Timestamp Validation

```python
# Source: https://docs.python.org/3.11/library/datetime.html
from datetime import UTC, datetime


def normalize_utc_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EventValidationError("timestamp must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EventValidationError("timestamp must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EventValidationError("timestamp must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
```

Python 3.11's parser accepts both `Z` and explicit offsets, while the explicit aware check prevents a naive local time from being mislabeled UTC. [CITED: https://docs.python.org/3.11/library/datetime.html]

### Strict Payload Registry

```python
# Source: Phase 11 D-01..D-04 and existing dataclass/__post_init__ pattern
@dataclass(frozen=True)
class PayloadSpec:
    required: frozenset[str]
    optional: frozenset[str] = frozenset()

    def validate_keys(self, payload: Mapping[str, object]) -> None:
        keys = frozenset(payload)
        missing = self.required - keys
        unknown = keys - self.required - self.optional
        if missing:
            raise EventValidationError("payload is missing required fields")
        if unknown:
            raise EventValidationError("payload contains unsupported fields")


PAYLOAD_SPECS = {
    EventType.RETRY_SCHEDULED: PayloadSpec(
        required=frozenset({
            "tool_name", "completed_attempt", "next_attempt",
            "max_attempts", "delay_seconds",
        }),
        optional=frozenset({"failure_kind"}),
    ),
}
```

Keep error text field-independent enough for public diagnostics, while unit tests can assert the typed diagnostic code such as `missing_payload_field` or `unsupported_payload_field`. [VERIFIED: D-05/D-18; recommended design]

### Fail-Open Sink, Fail-Closed Timeline

```python
# Source: Phase 11 D-05 and OWASP Logging Cheat Sheet
class EventCollector:
    def emit(self, event: RuntimeEvent) -> None:
        try:
            self.accept(event)
        except Exception as exc:
            # Never include str(exc) or the raw event in diagnostics.
            self._record_internal_failure(type(exc).__name__)

    def accept(self, event: RuntimeEvent) -> CollectionResult:
        received_at = self._clock()
        normalized = normalize_runtime_event(event)
        with self._lock:
            return self._commit(normalized, received_at)
```

OWASP specifically recommends that logging failures not prevent the application from otherwise running and that event data be validated/sanitized. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html]

### Atomic Per-Run Sequence Allocation

```python
# Source: https://docs.python.org/3.11/library/threading.html
def _commit(self, fact: NormalizedEvent, received_at: datetime) -> CollectionResult:
    current = self._runs.get(fact.run_id)
    if current is not None and current.summary.status in TERMINAL_STATUSES:
        return self._reject_locked("run_already_terminal", fact.run_id, received_at)

    sequence = 1 if current is None else current.summary.last_sequence + 1
    envelope = EventEnvelope.from_fact(
        fact,
        sequence=sequence,
        received_at=received_at,
    )
    self._append_and_replace_summary_locked(envelope)
    return CollectionResult.accepted(envelope)
```

The terminal check, sequence allocation, append, and summary replacement must remain within one lock acquisition. [CITED: https://docs.python.org/3.11/library/threading.html; VERIFIED: D-11/D-15]

### Correlation Passed Through Retry Callback

```python
# Source: existing ToolExecutor callback seam and Phase 11 D-07/D-09
correlation = ToolEventContext(
    call_id=make_call_id(run_id, step),
    tool_call_id=external_tool_call_id,
    batch_id=batch_id,
)

result = await self.executor.execute_explicit(
    action,
    tool,
    on_event=lambda event_type, data: self._emit_external(
        event_type,
        run_id,
        step,
        correlation=correlation,
        **data,
    ),
)
```

The closure reuses one immutable correlation value for every attempt and retry event. [VERIFIED: current `ToolExecutor` callback behavior and D-07]

## State of the Art

| Old Approach | Phase 11 Approach | Impact |
|--------------|-------------------|--------|
| `RuntimeEvent` with a free-form `data` dictionary | Preserve as source event, then normalize into strict `agentguard.event.v1` | Existing v0.3 consumers remain valid while later API/SSE receive one stable contract. [VERIFIED: current model and COMPAT-01] |
| Runtime-owned nested `data.sequence` | Collector-owned top-level per-run `sequence`; source value is diagnostic only | Ordering remains stable across producers and is ready for Phase 13 reconnect IDs. [VERIFIED: D-11/D-12 and roadmap] |
| Batch ID placed in `RuntimeEvent.run_id` | Real run ID plus independent top-level batch ID | Run summaries no longer split one logical run into synthetic batch runs. [VERIFIED: current `_emit_batch_event` and D-08] |
| Tool lifecycle grouped by `run_id + step` or external ID | Internal logical `call_id` plus preserved external `tool_call_id` | Retries, approvals, replay, duplicate external IDs, and batch members can be distinguished correctly. [VERIFIED: D-06..D-10] |
| Raw `value` and `error_message` in event data | Bounded preview and fixed safe summaries | Future JSONL/SSE/UI cannot accidentally expose those raw channels. [VERIFIED: current emitter and D-16..D-18] |
| Mutable in-memory sink list | Lock-protected bounded run index with immutable snapshots | Concurrent collection and memory limits become explicit. [VERIFIED: current sink and Phase 11 discretion] |

**Deprecated/outdated for the new console boundary:**

- Treating `JsonlEventSink` as the v0.4 history writer is out of date: it serializes legacy `RuntimeEvent.to_dict()` and Phase 12 must persist validated v1 envelopes instead. It remains valid for v0.3 compatibility. [VERIFIED: `src/agentguard/events/sinks.py`, Phase 11/12 boundary]
- Treating `data.sequence` as an external cursor is out of date: it remains only legacy checkpoint/report evidence. [VERIFIED: D-11/D-12]
- Treating exception messages as acceptable observability payload is out of date: v1 uses stable categories and summaries. [VERIFIED: D-18]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Initial preview limits of depth 4, 20 items per collection, 512 characters per string, and 200 total nodes are sufficient for useful local debugging while bounding work. | Architecture Pattern 7 | The preview may be too terse or too expensive; limits are injected/configurable constants and deterministic tests should make adjustment cheap. |

No external dependency, compliance, retention-duration, or performance guarantee is assumed by this research. [VERIFIED: phase scope and project honesty constraint]

## Open Questions (RESOLVED)

1. **Standalone `Runtime.execute_batch()` uses a distinct real run ID.**
   - Final choice: Add an optional keyword-only `run_id`. When callers omit it, generate a fresh opaque UUID-based batch-run ID once for that invocation; keep the existing caller-provided/generated `batch_id` as a separate correlation field and never place it in `RuntimeEvent.run_id`. [VERIFIED: D-08/D-10; Plan 11-02 Task 1]
   - Rationale: A batch is an execution grouping inside a run, not the run identity itself. The optional argument preserves existing call sites while correcting the old synthetic-identity behavior. [VERIFIED: D-08/D-10; Plan 11-02 Task 1]
   - Implementation/evidence: Plan 11-02 Task 1 updates the Runtime batch APIs and `_emit_batch_event`; Plan 11-02 Task 2 tests legacy calls, explicitly supplied correlation, and a deliberately different `run_id`/`batch_id`. [VERIFIED: Plan 11-02 Tasks 1-2]

2. **Sequential Runtime calls use a namespaced deterministic UUID5 `call_id`.**
   - Final choice: Derive the opaque internal `call_id` from a fixed AgentGuard UUID namespace plus only the non-secret logical `run_id` and `step`. Retries close over that same correlation object, and crash/checkpoint resume recomputes the same identifier without adding a checkpoint field. [VERIFIED: D-06/D-07/D-09/D-10; Plan 11-02 Task 1]
   - Rationale: The logical coordinates already survive checkpoint recovery, so UUID5 provides stable replay identity without hashing arguments, errors, approval data, or tool results and without broadening the checkpoint schema. [CITED: https://docs.python.org/3.11/library/uuid.html; VERIFIED: D-07/D-09; Plan 11-02 Task 1]
   - Implementation/evidence: Plan 11-02 Task 1 owns generation and propagation; Plan 11-02 Task 2 proves one `call_id` across retries and simulated crash/resume while distinct steps keep distinct IDs. Adapter batch correlation remains separately persisted in `_agentguard_prepared` by Plan 11-04 Task 1. [VERIFIED: Plan 11-02 Tasks 1-2; Plan 11-04 Task 1]

3. **Repeated non-terminal `run_started` is accepted as additional evidence without resetting the run summary.**
   - Final choice: While the run remains active, accept the repeated start as the next Collector event and allocate its normal next sequence, but preserve the existing `started_at`, status history, event counters, and prior timeline. A `run_started` received after a terminal `run_finished` remains rejected under D-15. [VERIFIED: D-13/D-14/D-15/D-21; Plan 11-03 Task 1]
   - Rationale: `Runtime.resume()` can legitimately produce `resume_started` followed by another source `run_started`; retaining both preserves at-least-once evidence, while resetting the summary would corrupt duration and chronology. Terminal runs must remain immutable and require a new run ID for new execution. [VERIFIED: D-13/D-15; Plan 11-03 Task 1]
   - Implementation/evidence: Plan 11-03 Task 1 encodes and tests duplicate non-terminal start, late-start backfill, resume transitions, and post-terminal rejection in the explicit Collector state machine. Plan 11-04 Task 2 exercises the real checkpoint/resume integration against that Collector behavior. [VERIFIED: Plan 11-03 Task 1; Plan 11-04 Task 2]

All three planning questions are resolved by Plans 11-02 through 11-04; they introduce no decision beyond D-01..D-21. [VERIFIED: Plans 11-02, 11-03, and 11-04]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Core contract/collector | ✓ via `python` | 3.12.9 | Project minimum is 3.11. [VERIFIED: local probe, `pyproject.toml`] |
| pytest | Automated tests | ✓ | 8.3.5 | Existing project range is `>=8,<10`. [VERIFIED: local package metadata, `pyproject.toml`] |
| pytest-asyncio | Runtime/adapter tests | ✓ | 0.24.0 | Existing project range is `>=0.24,<2`. [VERIFIED: local package metadata, `pyproject.toml`] |
| LangGraph | Optional adapter evidence | ✓ | 0.6.11 | Adapter tests already use import-skip when optional dependencies are absent. [VERIFIED: local package metadata, existing tests] |
| langchain-core | Optional adapter evidence | ✓ | 0.3.86 | Same optional extra as LangGraph. [VERIFIED: local package metadata, `pyproject.toml`] |
| FastAPI / Node frontend | Not required in Phase 11 | Not probed | — | Explicitly deferred; must not be imported by core. [VERIFIED: Phase 11 boundary and COMPAT-01] |

The source tree is not installed as a distribution in the active environment, but `PYTHONPATH=src` imports AgentGuard and the full baseline passes `136 passed`. [VERIFIED: local probe on 2026-09-06]

**Missing dependencies with no fallback:** None. [VERIFIED: environment audit]

**Missing dependencies with fallback:** The editable AgentGuard distribution is not installed; tests use `PYTHONPATH=src`, matching the repository's current verification commands. [VERIFIED: local probe and README]

## Security Domain

Security enforcement is enabled by default because `.planning/config.json` does not explicitly disable it. [VERIFIED: `.planning/config.json` and GSD workflow rule]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No authentication surface exists in Phase 11; login is out of scope. [VERIFIED: Phase 11 Deferred Ideas] |
| V3 Session Management | no | No browser/server session exists in Phase 11. [VERIFIED: Phase 11 boundary] |
| V4 Access Control | no new control | Existing Runtime permissions are observed, not re-authorized by Collector. [VERIFIED: phase boundary and existing `PermissionPolicy`] |
| V5 Input Validation | yes | Strict dataclass/enums, exact payload specs, UTC validation, safe projection, and rejection diagnostics. [VERIFIED: D-01..D-05] |
| V6 Cryptography | no new cryptographic control | Use standard UUID/hash primitives only as identifiers/digests, never as authentication or encryption. [VERIFIED: phase scope and existing digest semantics] |

The ASVS project provides a basis for testing web application technical security controls; Phase 11's relevant work is the data validation and protection boundary that later web phases will consume. [CITED: https://owasp.org/www-project-application-security-verification-standard/]

### Known Threat Patterns for the Event Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret disclosure through arguments/results/errors | Information Disclosure | Recursive key/value redaction, fixed error summaries, no raw exception/path/reason fields, strict allowlists. [CITED: OWASP Logging Cheat Sheet; VERIFIED: D-16..D-18] |
| Log/JSON injection through newline/control characters | Tampering | Normalize bounded strings, never concatenate raw event text, and require strict JSON-serializable structured values. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html] |
| Resource exhaustion via deep/wide/cyclic payloads | Denial of Service | Depth/item/string/total-node budgets, cycle detection, bounded event/run/diagnostic deques. [CITED: OWASP Logging Cheat Sheet verification guidance; VERIFIED: D-16 and discretion] |
| Timeline tampering via caller sequence/timestamp | Tampering | Collector assigns sequence under lock; timestamps are validated but never control timeline ordering. [VERIFIED: D-11..D-14] |
| Run resurrection after terminal status | Tampering / Repudiation | Reject every later ordinary event and retain a bounded diagnostic; new execution requires a new run ID. [VERIFIED: D-15] |
| Correlation collision/spoofing through external `tool_call_id` | Spoofing | Preserve it only as source evidence; use internal `call_id` as the logical key. [VERIFIED: D-06] |
| Collector failure interrupts Agent execution | Denial of Service | `emit()` catches `Exception`, records safe bounded diagnostics, and never invokes external code under its lock. [CITED: OWASP Logging Cheat Sheet; VERIFIED: D-05] |

OWASP recommends treating event data from different trust zones as untrusted, validating/sanitizing it, excluding or masking access tokens/passwords/keys, and testing logging failure/resource-exhaustion behavior. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html]

## Sources

### Primary (HIGH confidence)

- [Python 3.11 dataclasses documentation](https://docs.python.org/3.11/library/dataclasses.html) — generated methods, `__post_init__`, frozen instances, deep conversion behavior.
- [Python 3.11 datetime documentation](https://docs.python.org/3.11/library/datetime.html) — UTC singleton and ISO timestamp parsing including `Z`.
- [Python 3.11 threading documentation](https://docs.python.org/3.11/library/threading.html) — lock atomicity and context-manager use.
- [Python 3.11 asyncio synchronization documentation](https://docs.python.org/3.11/library/asyncio-sync.html) — asyncio primitives are not OS-thread safe.
- [Python 3.11 UUID documentation](https://docs.python.org/3.11/library/uuid.html) — random and name-based UUID generation.
- [Python 3.11 collections documentation](https://docs.python.org/3.11/library/collections.html#collections.deque) — bounded deque semantics.
- [Python 3.11 JSON documentation](https://docs.python.org/3.11/library/json.html) — circular checks and strict non-finite number handling.
- [Python 3.11 built-in exceptions documentation](https://docs.python.org/3.11/library/exceptions.html#BaseException) — `Exception` versus system-exiting `BaseException` subclasses.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — event validation, sensitive-data exclusion, failure isolation, and resource-exhaustion testing.
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) — application security verification scope.
- AgentGuard source and tests listed in `11-CONTEXT.md` — current producer, sink, redaction, checkpoint, adapter, and test behavior. [VERIFIED: codebase inspection]

### Secondary (MEDIUM confidence)

- None. The phase recommendation is based on locked project decisions, direct code inspection, and primary official documentation. [VERIFIED: research method]

### Tertiary (LOW confidence)

- None. Exact preview tuning is recorded as A1 rather than asserted as ecosystem fact. [VERIFIED: Assumptions Log]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new dependency; all selected primitives are Python standard library features documented for the project's minimum Python version. [CITED: Python 3.11 documentation; VERIFIED: `pyproject.toml`]
- Architecture: HIGH — all integration seams and current defects were inspected directly, and the design follows D-01..D-21. [VERIFIED: codebase and `11-CONTEXT.md`]
- Pitfalls: HIGH — each critical pitfall is either already present in current producer code or directly prohibited by a locked decision/OWASP guidance. [VERIFIED: codebase, Phase 11 context; CITED: OWASP Logging Cheat Sheet]
- Preview limit tuning: LOW — exact numeric limits are a starting hypothesis and must be validated with fixtures. [ASSUMED]

**Research date:** 2026-09-06
**Valid until:** 2026-10-06 for the standard-library/core architecture; re-check optional LangGraph integration versions if dependencies change. [VERIFIED: stable core design; project-pinned optional versions]
