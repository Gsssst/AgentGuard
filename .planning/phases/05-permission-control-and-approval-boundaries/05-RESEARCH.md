# Phase 5: Permission Control and Approval Boundaries - Research

**Researched:** 2026-09-01  
**Domain:** Local Python Agent Runtime tool authorization, approval pauses, and audit evidence  
**Confidence:** HIGH for integration with the existing Runtime; MEDIUM for the exact multi-capability policy precedence

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Tool capability tags
- **D-01:** 第一版使用固定的四个能力标签：`read`、`write`、`external`、`destructive`。
- **D-02:** 一个 Tool 可以拥有多个标签；例如发送邮件可以是 `{"external", "write"}`，删除文件可以是 `{"write", "destructive"}`。
- **D-03:** Tool 注册阶段校验标签；未知标签直接报错，不允许静默放行。后续只有在出现真实需求时再扩展标签集合。

### Permission policy
- **D-04:** 权限控制启用后采用显式允许列表（fail-closed）：只有满足策略的 Tool 才能执行，未被允许的能力默认拒绝。
- **D-05:** 未配置权限策略时保持 Phase 1–4 的旧行为，确保权限能力是可选的增量边界，不破坏现有 Runtime。
- **D-06:** 策略需要区分“明确禁止”和“允许人工审批”：例如 `allowed={"read"}`，`approval_required={"external", "destructive"}`。直接禁止的 Tool 立即以结构化权限错误终止，需要审批的 Tool 进入等待状态。

### Approval lifecycle
- **D-07:** 需要审批的 `CallTool` 在审批前不得执行，Runtime 进入 `WAITING_APPROVAL`，保存 pending Action 和恢复所需状态到 checkpoint，并发出 `approval_requested` 事件。
- **D-08:** 审批通过后通过显式 `resume()` 继续执行原始 Tool；审批拒绝后记录 `PermissionDenied` 并以明确停止原因结束运行。
- **D-09:** 第一版定义结构化 `ApprovalDecision` 对象，不引入用户认证和复杂 token 系统；审批可以包含 `approved`、`actor`、`reason` 等字段。

### Audit and approval binding
- **D-10:** 审批请求、通过和拒绝都进入现有 append-only JSONL 事件流，记录 Tool、所需能力、策略决策、`run_id`、`step`、审批主体和结果。
- **D-11:** 审计参数保留可读结构，但对敏感字段递归脱敏为 `[REDACTED]`。默认识别包含 `password`、`token`、`secret`、`api_key`、`access_key`、`private_key`、`authorization` 的字段名；Tool 后续可以声明额外敏感字段。
- **D-12:** `actor` 是可选的审计标识，不代表身份认证；未提供时可以使用 `local_user` 这样的本地默认标识。
- **D-13:** 审批结果必须绑定原始 Action 摘要。`action_digest` 至少覆盖 `tool_name`、规范化 `arguments`、能力标签、`run_id` 和 `step`；恢复时摘要不一致则拒绝继续，防止审批复用或参数篡改。

### the agent's Discretion
- 具体 Python 类型名称、枚举继承方式、异常层级、默认 `PermissionPolicy` 构造方式和事件字段顺序。
- `WAITING_APPROVAL` 与现有 `RunStatus`、checkpoint lifecycle 的最小兼容实现。
- 脱敏字段匹配的大小写、递归容器边界和摘要哈希算法，只要保持确定性、可测试且不泄露原始敏感值。

### Deferred Ideas (OUT OF SCOPE)
- 角色模型、RBAC/ABAC、用户认证和真实身份授权。
- 外部审批服务、前端审批 UI、多租户策略和远程审批通知。
- 并发执行、资源锁和读写冲突策略（属于 Phase 5 后续切片或独立阶段）。
- LangGraph/Pi 等框架适配器和 Java Control Plane。
- 跨进程、跨机器的审批状态存储与分布式一致性。
</user_constraints>

## Summary

The repository currently has a single async Runtime loop that proposes a typed `CallTool`, emits `ACTION_PROPOSED`, invokes `ToolExecutor`, records a bounded `RunState`, and writes optional checkpoints [VERIFIED: `src/agentguard/runtime/engine.py`; `src/agentguard/domain/actions.py`; `src/agentguard/domain/state.py`]. Phase 5 should insert authorization after action proposal and before `TOOL_STARTED`, while keeping the existing executor as the only side-effect boundary [VERIFIED: `05-CONTEXT.md` code context; `engine.py`].

The smallest compatible design is a standard-library permission policy plus immutable Tool capability metadata, a non-terminal `WAITING_APPROVAL` state, and a pending-action checkpoint that is resumed explicitly with an `ApprovalDecision` [VERIFIED: locked decisions D-01–D-13]. Approval must be a pause, not an executor call that is later audited; the Tool side effect must occur only after the decision and digest have been validated [VERIFIED: D-07, D-08, D-13].

The main planning risk is multi-label policy precedence. The prior discussion example treats `{"external", "write"}` as approval-gated when `external` is in `approval_required`, even though `write` is not in `allowed`; the planner should encode this behavior in tests and document the precedence explicitly [VERIFIED: Phase 5 discussion captured in `05-CONTEXT.md` specific ideas; MEDIUM confidence because the prose does not define every mixed-label case].

**Primary recommendation:** Add `Tool.capabilities` and registration validation, a fail-closed `PermissionPolicy` with explicit allow/approval decisions, a pause/resume path that persists pending Action plus digest, centralized recursive redaction and canonical hashing, new permission/approval events, and deterministic unit/integration scenarios. Use only Python standard-library code and preserve old behavior when no policy is supplied [VERIFIED: `pyproject.toml`; `05-CONTEXT.md`].

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Tool capability metadata and registration validation | API / Backend (Runtime library) | — | `ToolRegistry` owns Tool construction and is the earliest reliable boundary for rejecting unknown tags [VERIFIED: `src/agentguard/runtime/tool.py`; D-03]. |
| Permission decision (allow/deny/approval) | API / Backend (Runtime engine/policy) | — | The Runtime sees the proposed Action and must decide before invoking `ToolExecutor` [VERIFIED: `engine.py`; D-04, D-07]. |
| Approval state and pending Action persistence | API / Backend (Runtime/checkpoint DTO) | Database / Storage (local JSON file) | Runtime owns lifecycle and validation; the existing local checkpoint store persists explicit bytes [VERIFIED: `src/agentguard/checkpoint/model.py`; `store.py`; D-07]. |
| Approval audit events and redaction | API / Backend (events/reporting) | Storage (JSONL sink) | Existing `RuntimeEvent`/`EventSink` already define append-only evidence; new event data must be JSON-safe and redacted [VERIFIED: `src/agentguard/events/model.py`; `sinks.py`; D-10, D-11]. |
| Action digest binding | API / Backend (authorization utility) | — | Digest validation must happen before Router/Tool side effects and use the current Tool capability metadata [VERIFIED: D-13; existing `action_signature` pattern]. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---|---|---|---|
| Python `dataclasses` and `enum.StrEnum` | Python `>=3.11` required by project | Immutable `ApprovalDecision`, `PermissionPolicy`, capability and lifecycle enums | Existing domain contracts use dataclasses and `StrEnum`; no schema dependency is present [VERIFIED: `pyproject.toml`; `src/agentguard/domain`; `src/agentguard/runtime/policy.py`]. |
| `json` | Python standard library | Canonical Action digest input, checkpoint codec, and JSON-safe audit payloads | Existing checkpoint/events formats already use JSON; canonical JSON with sorted keys and compact separators is deterministic [VERIFIED: `src/agentguard/runtime/loop_guard.py`; `checkpoint/codec.py`; [CITED: https://docs.python.org/3/library/json.html]]. |
| `hashlib.sha256` | Python standard library | Stable, non-reversible Action binding digest | SHA-256 is available in the standard library and is appropriate for equality/binding evidence, not identity or authorization [CITED: https://docs.python.org/3/library/hashlib.html]. |
| `re`/string normalization plus recursive containers | Python standard library | Case-insensitive sensitive-key matching and `[REDACTED]` projection | Keeps redaction local and inspectable; no external data-masking package is required [VERIFIED: D-11; project has no runtime dependencies]. |

### Supporting

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| `pytest` + existing async test plugin | pytest 8.3.5 observed | Permission, approval, codec, and integration regression tests | Reuse current test layout and async fixtures; no new framework is needed [VERIFIED: `pytest --version`; `pyproject.toml`]. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| Capability labels + local policy | RBAC/ABAC identities | Richer multi-user authorization, but explicitly deferred and would require authenticated principals [VERIFIED: D-09; deferred ideas]. |
| Explicit `resume(..., ApprovalDecision)` | Background approval waiter or callback thread | Background waiting complicates bounded Runtime behavior and checkpoint semantics; explicit resume matches Phase 4 [VERIFIED: D-07, D-08; Phase 4 `04-LEARNINGS.md`]. |
| SHA-256 over canonical raw arguments | Digest of redacted arguments | Redacted values can collide or lose binding; hash the original canonical values and expose only the digest/redacted projection [VERIFIED: D-11, D-13; MEDIUM confidence]. |
| Existing local JSON/JSONL stores | Redis, database, remote approval service | Adds infrastructure and distributed consistency outside the locked local slice [VERIFIED: PROJECT.md; deferred ideas]. |

**Installation:** No external package is required. Run the existing environment with `PYTHONPATH=src pytest -q` using the available Python 3.12 interpreter [VERIFIED: `pyproject.toml`; environment probe].

## Architecture Patterns

### System Architecture Diagram

```text
Router.next_action(state)
        |
        v
ACTION_PROPOSED (audit-safe projection)
        |
        v
PermissionPolicy.decide(tool.capabilities)
   | allow                 | deny                         | approval
   v                       v                              v
ToolExecutor.execute   PERMISSION_DENIED             pending Action + digest
   |                       |                              |
   v                       v                              v
state.record/step++   failed RunResult              WAITING_APPROVAL
   |                                                      |
   +--> checkpoint + events <------------------------------+
                                                          |
                                resume(path, router, ApprovalDecision)
                                                          |
                         validate checkpoint + digest + decision
                                  | mismatch/invalid
                                  v
                           APPROVAL_REJECTED (no Tool call)
                                  |
                         approved: execute pending Action
                                  |
                             normal Runtime loop
```

### Recommended Project Structure

```text
src/agentguard/
├── runtime/
│   ├── permission.py   # Capability, PermissionPolicy, ApprovalDecision, digest/redaction
│   ├── tool.py         # Tool capabilities and registration validation
│   └── engine.py       # pre-execution decision and pending-action resume path
├── domain/
│   └── state.py        # WAITING_APPROVAL and explicit permission stop reason
├── checkpoint/
│   ├── model.py        # pending approval metadata/lifecycle
│   └── codec.py        # strict serialization of new fields
├── events/
│   └── model.py        # approval/permission event types
└── reporting/
    └── report.py       # approval/denial counters and evidence consistency
tests/
├── unit/test_permissions.py
├── unit/test_redaction_and_digest.py
├── unit/test_checkpoint.py  # waiting state round-trip
└── integration/test_permission_approval.py
```

### Pattern 1: Capability metadata is immutable and validated at registration

**What:** Store a `frozenset` of capability strings on each `Tool`; reject non-string, empty, or unknown values in `Tool.__post_init__`/`ToolRegistry.register` before the Tool becomes callable [VERIFIED: D-01–D-03; existing Tool validation pattern].

**When to use:** Every Tool registration, including test fixtures and resumed Runtime construction.

```python
CAPABILITIES = frozenset({"read", "write", "external", "destructive"})

@dataclass(frozen=True)
class Tool:
    name: str
    function: ToolCallable
    capabilities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        labels = frozenset(self.capabilities)
        if not labels <= CAPABILITIES:
            raise ValueError("unknown Tool capability")
        object.__setattr__(self, "capabilities", labels)
```

The exact default for an unlabelled Tool is discretionary; the safest compatibility choice is an empty set when no policy is configured, while a configured policy should fail closed for that Tool [ASSUMED; planner must add an explicit test].

### Pattern 2: Three-way policy decision with fail-closed fallback

**What:** Evaluate a `CallTool` after lookup and before `TOOL_STARTED`: allow only when all labels are in `allowed`; route to approval when the action matches the configured approval trigger; otherwise return a structured denial [VERIFIED: D-04, D-06; mixed-label precedence remains MEDIUM confidence].

**When to use:** Every `CallTool` when `permission_policy` is not `None`; skip the decision entirely when no policy is configured to preserve D-05.

Recommended decision table for the discussed first slice:

| Tool capabilities | `allowed={read}` / `approval_required={external, destructive}` | Result |
|---|---|---|
| `{read}` | all required labels allowed | execute |
| `{write}` | no allowed or approval trigger | direct denial |
| `{external, write}` | approval trigger present | wait for approval |
| `{destructive, write}` | approval trigger present | wait for approval |
| `{read, write}` | unapproved `write` remains | direct denial |

The last two mixed-label rows must be confirmed by tests during planning; do not let set iteration order decide the result [ASSUMED].

### Pattern 3: Pause with pending Action, then explicit approval resume

**What:** On approval-required action, do not call the executor. Compute and persist an `action_digest`, set `RunStatus.WAITING_APPROVAL`, store `pending_action` and approval metadata in the checkpoint, emit `approval_requested`, and return a non-terminal run projection [VERIFIED: D-07, D-10, D-13]. On resume, validate the checkpoint and supplied `ApprovalDecision` before executing the pending Action [VERIFIED: Phase 4 validate-before-side-effect pattern].

**When to use:** Any action requiring approval; approval rejection and digest mismatch are terminal/no-side-effect branches.

`resume()` should consume the pending Action once. An approved resume must execute that exact Action before asking the Router for another Action; otherwise a state-dependent Router could substitute a different call [ASSUMED; add integration test].

### Pattern 4: Canonical digest over raw arguments, redacted projection for events

**What:** Reuse the existing canonicalization rules (sorted mappings, explicit tuple representation, JSON-compatible scalars/containers), then hash a payload containing `tool_name`, canonical raw `arguments`, sorted capability labels, `run_id`, and `step` with SHA-256 [VERIFIED: `runtime/loop_guard.py`; D-13]. Use a separate recursive redaction function for event/checkpoint display data; never hash the redacted form [VERIFIED: D-11, D-13].

**When to use:** At approval request and again immediately before approved execution.

```python
payload = {
    "tool_name": action.tool_name,
    "arguments": canonicalize(action.arguments),
    "capabilities": sorted(tool.capabilities),
    "run_id": state.run_id,
    "step": state.step,
}
encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
digest = "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
```

### Pattern 5: Audit-safe event extensions and evidence-derived reporting

**What:** Add explicit `approval_requested`, `approval_granted`, `approval_denied`, and direct `permission_denied` event types while retaining existing event fields. Include tool name, required capabilities, policy decision, run/step, actor, reason, digest, and recursively redacted arguments [VERIFIED: D-10, D-11, D-12]. Extend `ReliabilityReport` with defaulted approval/denial counters so Phase 1–4 callers remain source-compatible [VERIFIED: `report.py`; existing dataclass defaults].

**When to use:** Every permission branch; derive counts from events instead of hidden mutable counters [VERIFIED: Phase 4 evidence-driven reporting pattern].

### Anti-Patterns to Avoid

- **Checking permissions inside `ToolExecutor`:** the executor cannot distinguish Router intent, pending approval, and Runtime checkpoint state; it also makes direct denial harder to guarantee before `TOOL_STARTED` [VERIFIED: existing integration boundary; D-07].
- **Executing first and requesting approval afterward:** violates the explicit no-side-effect approval boundary [VERIFIED: D-07].
- **Hashing redacted parameters:** removes the binding to the actual call and can allow a modified Action to reuse an approval [VERIFIED: D-11, D-13].
- **Treating `actor` as authenticated identity:** the first version has no authentication and must label the value as audit metadata only [VERIFIED: D-09, D-12].
- **Resetting pending Action by asking Router first on resume:** can execute a different action than the one approved [ASSUMED; test as a safety invariant].
- **Making `WAITING_APPROVAL` terminal without an explicit resume contract:** callers cannot distinguish a paused run from a failed run, and checkpoint lifecycle semantics become ambiguous [ASSUMED; resolve in plan].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Canonical serialization | Ad-hoc string concatenation or `repr(arguments)` | Existing `canonicalize` + `json.dumps(sort_keys=True, separators=...)` | Stable key ordering and explicit container handling are already implemented and tested for action signatures [VERIFIED: `runtime/loop_guard.py`; `tests/unit/test_loop_guard.py`]. |
| Cryptographic digest primitive | Custom checksum or reversible encoding | `hashlib.sha256` over canonical JSON | Standard-library implementation avoids ambiguous custom hashing; digest is binding evidence, not authentication [CITED: https://docs.python.org/3/library/hashlib.html]. |
| JSON event persistence | New audit database or bespoke log writer | Existing `RuntimeEvent` and `JsonlEventSink` | Append-only JSONL and event serialization are already established [VERIFIED: `events/model.py`; `events/sinks.py`]. |
| Checkpoint durability | Permission-specific storage protocol | Existing `CheckpointStore` atomic JSON replacement | Approval state must use the same validate-before-side-effect and local atomic boundary as recovery [VERIFIED: Phase 4 `04-LEARNINGS.md`; `checkpoint/store.py`]. |
| Identity/authorization | Homemade user/session authentication | Explicit local `actor` label only | Authentication and RBAC are explicitly deferred [VERIFIED: D-09, D-12; deferred ideas]. |

**Key insight:** Permission control is an ordering contract. The meaningful guarantee is “the Tool was not entered before the policy, approval decision, checkpoint, and digest checks passed,” which is testable with a side-effect counter [VERIFIED: D-07, D-13; Phase 4 UAT pattern].

## Common Pitfalls

### Pitfall 1: Ambiguous multi-capability precedence

**What goes wrong:** A Tool with both approved and unapproved labels is inconsistently allowed or denied depending on set iteration order [ASSUMED].  
**Why it happens:** `allowed` and `approval_required` are sets, but the context does not define whether approval is any-label or all-label [VERIFIED: D-06; MEDIUM confidence].  
**How to avoid:** Implement a named decision function and table-driven tests for `{read,write}`, `{external,write}`, `{destructive,write}`, and unknown/unlabelled tools; fail closed for uncovered labels [RECOMMENDED based on D-04, D-06].  
**Warning signs:** A policy decision changes after refactoring or produces different outcomes for equivalent frozensets.

### Pitfall 2: Approval pause accidentally executes the Tool

**What goes wrong:** `TOOL_STARTED`, executor calls, or side-effect counters appear before `approval_requested`/checkpoint [VERIFIED risk from D-07].  
**Why it happens:** Permission logic is placed after the existing `TOOL_STARTED` emission or inside `ToolExecutor` [VERIFIED: current engine ordering].  
**How to avoid:** Place the decision immediately after `ACTION_PROPOSED`; return/persist waiting state before the executor path [VERIFIED: D-07].  
**Warning signs:** Approval-required integration test sees a non-zero Tool call count.

### Pitfall 3: Sensitive data leaks through a different event field

**What goes wrong:** Approval events redact `arguments`, but `ACTION_PROPOSED` or checkpoint fields still contain the raw secret [ASSUMED].  
**Why it happens:** Existing `ACTION_PROPOSED` stores raw `action.arguments` and checkpoint codec stores raw Action arguments [VERIFIED: `engine.py`; `checkpoint/codec.py`].  
**How to avoid:** Decide and test an explicit audit policy: at minimum redact all approval event payloads; preferably use a redacted action projection for `ACTION_PROPOSED` when permission mode is enabled while retaining raw values only in-memory for digesting [RECOMMENDED; requires compatibility review].  
**Warning signs:** Searching JSONL/checkpoint text for `password`, `token`, or known secret values finds a match.

### Pitfall 4: Digest computed from display data or incomplete context

**What goes wrong:** Approval remains valid after argument, capability, step, or run identity changes [VERIFIED risk from D-13].  
**Why it happens:** Digest omits fields, hashes redacted arguments, or uses non-canonical JSON [VERIFIED: D-11, D-13; existing `action_signature` pattern].  
**How to avoid:** Include all five required components, sort capability labels, canonicalize arguments, and recompute immediately before execution; mismatch must stop before Router/Tool side effects [VERIFIED: D-13].  
**Warning signs:** Two differently ordered argument dictionaries produce different digests, or a modified checkpoint is accepted.

### Pitfall 5: Resume invokes Router before consuming approved pending Action

**What goes wrong:** The Router proposes a new action while an old action has already been approved, so the approved call is skipped or a different side effect occurs [ASSUMED].  
**Why it happens:** Existing `Runtime.resume()` restores state and immediately enters `run()`, which calls `router.next_action` [VERIFIED: `engine.py`].  
**How to avoid:** Add an internal one-shot pending-action path; consume and clear it only after digest/decision validation, then continue the normal loop [RECOMMENDED based on D-07, D-08, D-13].  
**Warning signs:** Approved Tool call count is zero or Router call count increases before `approval_granted`.

### Pitfall 6: Treating a waiting checkpoint as ordinary crash recovery

**What goes wrong:** Calling `resume(path, router)` without an ApprovalDecision executes a previously gated Tool [VERIFIED risk from D-07].  
**Why it happens:** Phase 4 `resume()` currently accepts any non-terminal checkpoint [VERIFIED: `engine.py`; `checkpoint/model.py`].  
**How to avoid:** Add a distinct waiting lifecycle or an explicit `approval_pending` marker and require a validated decision for that checkpoint; reject missing/mismatched decisions without side effects [RECOMMENDED based on D-07, D-13].  
**Warning signs:** A waiting checkpoint can be resumed using the old Phase 4 API alone.

## Code Examples

### Recursive redaction

```python
SENSITIVE_MARKERS = (
    "password", "token", "secret", "api_key", "access_key",
    "private_key", "authorization",
)

def redact(value: object, *, extra_keys: set[str] = frozenset()) -> object:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            sensitive = any(marker in lowered for marker in SENSITIVE_MARKERS)
            sensitive = sensitive or lowered in {name.lower() for name in extra_keys}
            result[key] = "[REDACTED]" if sensitive else redact(item, extra_keys=extra_keys)
        return result
    if isinstance(value, list):
        return [redact(item, extra_keys=extra_keys) for item in value]
    if isinstance(value, tuple):
        return [redact(item, extra_keys=extra_keys) for item in value]
    return value
```

This projection is for display/audit only; digest input must use the unredacted canonical value [VERIFIED: D-11, D-13].

### Approval decision validation boundary

```python
decision = approval_decision
if decision is None:
    raise ApprovalRequiredError("approval decision is required")
if decision.action_digest != expected_digest:
    raise ApprovalDigestMismatchError("approval does not match pending action")
emit(APPROVAL_GRANTED if decision.approved else APPROVAL_DENIED, ...)
if not decision.approved:
    return finish_permission_denied(state)
# Only now invoke the pending Action through ToolExecutor.
```

The exact exception classes are discretionary, but all validation must happen before any Tool invocation [VERIFIED: D-08, D-13; Phase 4 validate-before-side-effect pattern].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Every proposed Tool enters the executor | Runtime evaluates immutable capability labels before `TOOL_STARTED` | Phase 5 locked decision, 2026-09-01 [VERIFIED: D-01–D-07] | Unauthorized side effects are prevented and explainable. |
| Approval represented by an out-of-band boolean | Structured `ApprovalDecision` bound to a canonical Action digest | Phase 5 locked decision, 2026-09-01 [VERIFIED: D-09, D-13] | A decision can be audited and cannot silently transfer to another call. |
| Raw arguments in audit evidence | Readable recursive projection with sensitive fields replaced | Phase 5 locked decision, 2026-09-01 [VERIFIED: D-10, D-11] | Debug evidence remains useful without default secret disclosure. |
| Crash recovery only | Crash recovery plus a distinct approval pause/resume branch | Phase 5 depends on Phase 4, 2026-09-01 [VERIFIED: Phase 4 `04-LEARNINGS.md`; D-07, D-08] | Checkpoint lifecycle now has two reasons for explicit continuation. |

**Deprecated/outdated:** In this project, direct executor calls without a preceding policy decision are incompatible with the Phase 5 boundary when a policy is configured [VERIFIED: D-04, D-07]. RBAC, authentication, distributed approvals, and framework adapters remain deferred [VERIFIED: deferred ideas].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | An unlabelled Tool uses an empty capability set for backward compatibility when no policy is configured, but is denied when a policy is configured unless explicitly allowed by a defined default rule. | Pattern 1 | Existing callers may expect a default label or policy may accidentally allow an unlabelled side effect. |
| A2 | A mixed-label Tool is approval-gated when it contains an `approval_required` label, matching the prior `external + write` discussion example. | Summary; Pattern 2 | If policy requires every label to be covered, the implementation and tests need a stricter all-label rule. |
| A3 | `WAITING_APPROVAL` is represented as a `RunStatus` value and a distinct checkpoint lifecycle or approval marker, while a waiting `RunResult` is a resumable projection rather than terminal success/failure. | Pattern 3; Pitfall 6 | Existing `RunResult` invariants may need a compatible new type or status semantics. |
| A4 | Raw Action arguments can remain in memory for digesting but must not be emitted into approval audit events; whether `ACTION_PROPOSED` is redacted under policy mode needs an explicit compatibility decision. | Pitfall 3 | Secrets may remain in JSONL/checkpoints or existing consumers may break if event payloads change. |
| A5 | The Tool registry available during resume is authoritative for current capabilities; capability changes cause digest mismatch and safe rejection. | Pattern 4 | A persisted capability snapshot may be required for controlled migrations. |

## Open Questions

1. **Should a mixed-label Tool require every label to be allowed/approved, or should any approval-required label gate the entire action?**
   - What we know: The discussion example treats `external + write` as approval-gated with `allowed={read}` and `approval_required={external, destructive}` [VERIFIED: `05-CONTEXT.md` specific ideas; MEDIUM confidence].
   - What's unclear: The fail-closed wording could also be interpreted as all labels needing coverage [VERIFIED: D-04, D-06].
   - Recommendation: Preserve the discussed behavior for this phase (approval trigger wins over uncovered labels) and add explicit table-driven tests; revisit only if the user changes the decision [RECOMMENDED].

2. **How should a paused run be represented without breaking `RunResult`'s terminal contract?**
   - What we know: Current `RunStatus` has only RUNNING/COMPLETED/FAILED, and `RunResult` rejects only RUNNING [VERIFIED: `src/agentguard/domain/state.py`; `domain/runtime.py`].
   - What's unclear: Whether to add `WAITING_APPROVAL` to `RunStatus`, introduce a separate `ApprovalPending` result, or keep a recoverable checkpoint while returning a specialized object [VERIFIED: D-07; discretion].
   - Recommendation: Add `WAITING_APPROVAL` as an explicit status and update result/report/checkpoint invariants in one compatibility-focused task; never encode waiting as failed [RECOMMENDED].

3. **Should `ACTION_PROPOSED` and checkpoint pending arguments be redacted?**
   - What we know: Existing `ACTION_PROPOSED` and checkpoint codecs currently carry raw Action arguments [VERIFIED: `engine.py`; `checkpoint/codec.py`]. Approval events must be redacted [VERIFIED: D-11].
   - What's unclear: Whether changing existing event payloads is acceptable in the first permission-enabled mode [VERIFIED: D-05; discretion].
   - Recommendation: Keep raw arguments only in the in-memory domain object for digesting; emit a redacted `arguments` field for all policy-enabled action/approval events and add a separate `arguments_digest`/`action_digest` for correlation [RECOMMENDED; planner should preserve no-policy compatibility].

4. **Should an approval decision be persisted after grant/denial?**
   - What we know: The request and result must be appended to JSONL, and the pending Action must be checkpointed [VERIFIED: D-07, D-10].
   - What's unclear: Whether to retain decision metadata in the final checkpoint or only in the event stream [VERIFIED: D-10; discretion].
   - Recommendation: Retain a compact decision projection (`approved`, `actor`, `reason`, digest) in the checkpoint until terminal lifecycle update so a final file is self-explanatory; never persist raw unredacted arguments there [RECOMMENDED].

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---:|---|---|
| Python runtime | Runtime and codec changes | ✓ | `python` 3.12.9 | — |
| `python3` command | Convenience only | ✓ (wrong version) | 3.9.6; below project `>=3.11` | Use `python`/Miniforge interpreter [VERIFIED: environment probe; `pyproject.toml`]. |
| pytest | Unit/integration verification | ✓ | 8.3.5 | — |
| pytest-asyncio | Existing async tests | ✓ (tests currently collect/run) | Version not queried | Use existing async test setup; if unavailable, run `asyncio.run` smoke tests [ASSUMED]. |
| Redis/PostgreSQL/RabbitMQ/external approval service | None in locked phase | Not required | — | Do not add services [VERIFIED: PROJECT.md; deferred ideas]. |

**Missing dependencies with no fallback:** None for the locked local scope.  
**Missing dependencies with fallback:** `python3` 3.9 is below the project requirement; use the available Python 3.12 interpreter.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | no | Authentication is explicitly out of scope; `actor` is an untrusted audit label [VERIFIED: D-09, D-12]. |
| V3 Session Management | no | `run_id` correlates a local run and is not a session credential [VERIFIED: existing `RunState`; D-12]. |
| V4 Access Control | yes | Enforce capability allow/approval policy before executor entry; direct denial must be fail-closed [VERIFIED: D-03–D-07; ASVS access-control category [CITED: https://github.com/OWASP/ASVS]]. |
| V5 Input Validation | yes | Validate Tool labels, policy labels, ApprovalDecision fields, checkpoint lifecycle, digest, and redaction inputs before side effects [VERIFIED: D-03, D-07, D-13]. |
| V6 Cryptography | limited | Use `hashlib.sha256` only for action-binding integrity; do not represent it as authentication, encryption, or authorization [VERIFIED: D-13; [CITED: https://docs.python.org/3/library/hashlib.html]]. |

### Known Threat Patterns for local Python Runtime

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Unauthorized Tool side effect | Elevation of privilege / Tampering | Evaluate labels before `TOOL_STARTED`; deny or pause without executor call [VERIFIED: D-04, D-07]. |
| Approval replay for changed arguments | Tampering | Recompute canonical digest over Tool, arguments, capabilities, run ID, and step immediately before execution [VERIFIED: D-13]. |
| Secret leakage in audit files | Information disclosure | Recursive case-insensitive marker redaction; test nested dict/list payloads and scan JSONL/checkpoint text [VERIFIED: D-11]. |
| Forged `actor` field | Spoofing | Document actor as caller-provided metadata, not authenticated identity; defer auth [VERIFIED: D-09, D-12]. |
| Waiting checkpoint resumed without consent | Elevation of privilege | Require an ApprovalDecision for waiting lifecycle and validate before Router/Tool calls [RECOMMENDED from D-07]. |
| Unknown capability silently accepted | Elevation of privilege | Reject labels at registration and policy construction; use a finite enum/set [VERIFIED: D-01–D-03]. |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/05-permission-control-and-approval-boundaries/05-CONTEXT.md` — all locked Phase 5 decisions, examples, and deferred scope [VERIFIED: codebase read].
- `src/agentguard/runtime/engine.py`, `runtime/tool.py`, `runtime/loop_guard.py`, `domain/state.py`, `domain/runtime.py` — existing execution ordering, Tool registry, canonicalization, and status/result contracts [VERIFIED: codebase read].
- `src/agentguard/checkpoint/{model,codec,store}.py`, `events/{model,sinks}.py`, `reporting/report.py` — persistence, event, and evidence integration points [VERIFIED: codebase read].
- `.planning/phases/04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra/04-LEARNINGS.md` — validate-before-side-effect, explicit resume, atomic checkpoint, and evidence-derived reporting patterns [VERIFIED: codebase read].

### Secondary (MEDIUM confidence)

- Python standard-library documentation for JSON and SHA-256 (`json`, `hashlib`) — API behavior and canonical serialization primitives [CITED: https://docs.python.org/3/library/json.html; https://docs.python.org/3/library/hashlib.html].
- OWASP ASVS access-control and validation categories — security review vocabulary for this local authorization boundary [CITED: https://github.com/OWASP/ASVS].

### Tertiary (LOW confidence)

- None required for the locked local implementation; mixed-label precedence and waiting-result compatibility are explicitly recorded as assumptions/open questions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — project requires Python >=3.11, uses only standard library, and no package installation is needed [VERIFIED: `pyproject.toml`; source tree].
- Architecture: HIGH — insertion point and reusable persistence/event boundaries are visible in existing code and locked decisions [VERIFIED: `engine.py`; `05-CONTEXT.md`].
- Policy semantics: MEDIUM — the discussed mixed-label example is clear, but D-04's all-label fail-closed wording leaves one precedence detail to make explicit in tests.
- Security pitfalls: MEDIUM — threats are direct consequences of the side-effect ordering and audit requirements; no external identity system is in scope.

**Research date:** 2026-09-01  
**Valid until:** 2026-10-01 for stable Python standard-library APIs; revisit sooner if the Runtime status/checkpoint contract changes.
