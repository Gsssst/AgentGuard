# Phase 9: Approval Bridge and Compatibility Evidence - Research

**Researched:** 2026-09-03
**Domain:** LangGraph `interrupt`/`Command(resume=...)` human-in-the-loop bridge for a Python tool adapter
**Confidence:** HIGH for public API semantics and repository boundaries; MEDIUM for the final adapter shape (implementation discretion)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 审批中断与批次执行
- **D-01:** 一个批次中先执行无需审批的调用，再将所有待审批调用集中到一次 LangGraph `interrupt`；不得让安全调用因其他调用待审批而无条件暂停。
- **D-02:** 待审批调用在中断前不申请或持有资源锁。直接调用完成后构造中断；恢复后，获批调用重新通过 AgentGuard 的权限、资源锁、timeout、retry 和审计边界。
- **D-03:** 一次 `interrupt` 携带待审批调用列表，每项保持独立的 `tool_call_id`、工具和审批绑定信息，审批者可在一次交互中分别决定。
- **D-04:** 直接允许调用即使失败，也只产生自己的结构化结果，不阻止其他调用进入审批中断。

#### interrupt 载荷与脱敏
- **D-05:** 每个待审批项只暴露最小但可审计的信息：`tool_call_id`、工具名、递归脱敏的参数摘要、所需 capabilities、资源 ID 与访问模式，以及独立 action digest。
- **D-06:** 参数摘要复用 AgentGuard 现有 `redact()` 规则，包括嵌套对象；不得在 interrupt 载荷中暴露原始密码、token、secret、API key、private key 或 authorization 值。
- **D-07:** 资源摘要展示业务资源 ID 和 `read` / `write` / `destructive` 访问模式，但不暴露锁持有者、等待者、线程或锁对象内部状态。
- **D-08:** 中断载荷增加稳定批次摘要，至少包含 `batch_id`、待审批数量和载荷版本；批次摘要不能替代每个调用自己的 digest。

#### Command(resume=...) 与部分批准
- **D-09:** 恢复数据按 `tool_call_id` 映射独立的审批决定；每项可包含 `approved`、`actor`、`reason` 和 `action_digest`，并分别进入审计证据。
- **D-10:** 恢复数据缺少某个待审批调用的决定时，该调用默认拒绝；只执行明确批准的调用，绝不默认放行。
- **D-11:** 部分批准恢复后仍为原始 `tool_calls` 中的每个调用返回一个结果，并严格保持原始输入顺序。拒绝或缺少决定的调用返回结构化 `PermissionDenied`；批准调用返回其实际成功或失败结果。
- **D-12:** 每个待审批调用使用保存的工具名、原始参数、capabilities、`run_id` 和原始调用索引重新计算 digest。单项 digest 不匹配只拒绝该调用，不影响其他调用的校验和执行。

#### 兼容性证据与学习记录
- **D-13:** 第一版锁定并记录本地实际验证的 `langgraph` 与 `langchain-core` 版本，完成干净环境可选依赖安装和真实 `StateGraph` interrupt/resume 证据；不宣称支持所有历史版本。
- **D-14:** 故障测试覆盖审批通过、明确拒绝、缺少决定、digest 不匹配、参数篡改、恢复时工具不存在、敏感参数脱敏，以及批准后工具自身执行失败。
- **D-15:** 生成两份结构对应的学习记录：中文和英文各一份，均记录设计选择、主动故障、调试/修复、测试证据和已知限制。
- **D-16:** 未安装 LangGraph 可选依赖时，核心 AgentGuard 测试继续运行，真实集成测试以明确原因和安装提示跳过；依赖已安装时真实集成测试必须执行，不能无故跳过。

### the agent's Discretion
- interrupt payload、resume DTO 和辅助 dataclass 的具体公开名称及 JSON 字段顺序，只要满足上述稳定语义并使用 LangGraph 公共 API。
- 如何在一次 Node 调用内部保存直接调用结果以配合 LangGraph replay 语义，但不得新增第二套持久 checkpoint，也不得让直接调用在恢复重放时产生未声明的重复副作用。
- 当前已验证依赖版本的精确约束表达方式（精确 pin 或有界范围），以干净环境测试证据为准。
- 中英文学习记录的文件名和章节标题，只要两份内容一一对应且均包含主动故障证据。

### Deferred Ideas (OUT OF SCOPE)
- 审批者身份认证、RBAC/ABAC、签名 token、前端审批 UI、外部审批服务和远程通知。
- 多轮保持 pending、部分决定后再次 interrupt；第一版缺失决定直接拒绝。
- 分布式 checkpoint、跨进程锁、exactly-once 副作用和生产级高可用。
- 广泛 LangGraph 历史版本矩阵；第一版只承诺实际验证的有界版本。
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research support |
|----|-------------|------------------|
| APPROVAL-01 | Approval calls pause via LangGraph `interrupt` before invocation | Public interrupt semantics and pre-side-effect partition pattern |
| APPROVAL-02 | Interrupt contains redacted summary, call ID and digest | Existing `redact()`/`action_digest()` plus versioned payload contract |
| APPROVAL-03 | Resume uses `Command(resume=...)`, LangGraph owns checkpoint/recovery | Checkpointer and `thread_id` requirements verified in official docs |
| APPROVAL-04 | Independent approve/reject by `tool_call_id` | Resume DTO map and missing-decision fail-closed normalization |
| APPROVAL-05 | Digest recomputation rejects changed calls | Canonical digest inputs and per-call mismatch isolation |
| APPROVAL-06 | Only approved calls execute; denied calls become structured messages | Reuse Runtime explicit batch and existing ToolMessage conversion |
| COMPAT-03 | Real integration tests run when optional dependencies exist, otherwise skip clearly | Import-skip pattern and clean StateGraph test matrix |
| COMPAT-04 | Automated success/denial/timeout/retry/lock/approval/digest coverage | Deterministic fake tests plus real graph interrupt smoke test |
| COMPAT-05 | Chinese and English learning notes with deliberate failures and limits | Paired evidence document checklist |
</phase_requirements>

## Summary

LangGraph's public `interrupt(value)` raises a resumable graph interruption, persists state through the compiled graph checkpointer, and returns the resume value when the same `thread_id` is invoked with `Command(resume=...)` [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]. The node is restarted from its beginning on resume, so any work before `interrupt()` runs again; official guidance requires such side effects to be idempotent or moved to a separate node [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]. This is the central design constraint for combining direct (non-approval) calls with an approval batch.

The adapter should remain a thin translation layer. It should normalize calls, classify each call with `PermissionPolicy`, execute direct calls through the existing Runtime boundary, build one JSON-serializable redacted approval projection for pending calls, then validate per-call resume decisions and delegate approved calls to the explicit batch executor. LangGraph remains the only owner of graph state/checkpoint/replay; AgentGuard supplies policy, digest, timeout/retry, resources and audit evidence [VERIFIED: codebase; CITED: https://docs.langchain.com/oss/python/langgraph/persistence].

**Primary recommendation:** Use one versioned interrupt payload carrying all pending calls, key resume decisions by original `tool_call_id`, fail closed for missing or mismatched decisions, and isolate direct execution from the interrupt replay (prefer a preceding graph node or a persisted state projection over non-idempotent work in the interrupting node).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Approval pause/resume and thread checkpoint | API / Backend (LangGraph graph runtime) | Adapter | LangGraph's checkpointer and `thread_id` own suspension and recovery [CITED: https://docs.langchain.com/oss/python/langgraph/persistence]. |
| Tool-call normalization and message projection | API / Backend (AgentGuard adapter) | LangChain Core message types | Adapter translates `AIMessage.tool_calls` to `CallTool` and emits `ToolMessage` while preserving IDs [VERIFIED: codebase]. |
| Capability decision and digest binding | API / Backend (AgentGuard Runtime) | Adapter | Existing `PermissionPolicy`, `redact`, and `action_digest` are side-effect-free policy/evidence primitives [VERIFIED: codebase]. |
| Resource lock, timeout, retry and execution | API / Backend (AgentGuard Runtime) | LangChain tool | `Runtime.execute_explicit_tool/batch` and `ToolExecutor` are the single execution boundary [VERIFIED: codebase]. |
| Approval/audit evidence | API / Backend (AgentGuard events) | LangGraph state | Existing append-only Runtime events record approval requested/granted/denied; no second checkpoint is needed [VERIFIED: codebase]. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langgraph` | 0.6.11 (local environment) | `StateGraph`, `interrupt`, graph checkpointer integration | Current installed package and public graph APIs used by the adapter [VERIFIED: local package metadata; CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]. |
| `langchain-core` | 0.3.86 (local environment) | `AIMessage`, `ToolMessage`, `RunnableConfig` | Current installed message/runnable types used by `GuardedToolNode` [VERIFIED: local package metadata; VERIFIED: codebase]. |
| AgentGuard Runtime | repository source | permission, digest, resource lock, timeout/retry, audit | Existing boundary is required by Phase 9 decisions; do not bypass it [VERIFIED: codebase]. |

### Supporting

| Library/API | Version | Purpose | When to Use |
|-------------|---------|---------|-------------|
| `langgraph.checkpoint.memory.MemorySaver` / `InMemorySaver` | 0.6.11 API | Deterministic in-process checkpointer for tests | Real integration tests; use a durable checkpointer only outside this local evidence scope [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]. |
| `langgraph.types.interrupt` | 0.6.11 API | Surface redacted approval payload and suspend node | Call exactly once for the pending-call list [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]. |
| `langgraph.types.Command` | 0.6.11 API | Resume graph with decision map | Invoke with same `configurable.thread_id` and `Command(resume=...)` [CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]. |

No new third-party package is required for this phase; the existing optional `langgraph` extra is sufficient [VERIFIED: codebase `pyproject.toml`].

## Package Legitimacy Audit

This phase does not add a package. The optional packages already declared by the project were checked in the local Python environment; clean-install verification belongs in the phase plan/test task.

| Package | Registry | Version observed | slopcheck | Disposition |
|---------|----------|------------------|-----------|-------------|
| `langgraph` | PyPI | 0.6.11 | Not run (no install requested) | Existing optional dependency; verify in clean environment |
| `langchain-core` | PyPI | 0.3.86 | Not run (no install requested) | Existing optional dependency; verify in clean environment |

## Architecture Patterns

### System Architecture Diagram

```text
AIMessage.tool_calls + LangGraph state/thread_id
                |
                v
      GuardedToolNode: normalize + classify
        /             |                 \
 invalid/unknown  direct allow       approval-required
   safe result       Runtime batch       build redacted payload
        |                |                    |
        |                |             interrupt(payload)
        |                |                    |
        |                |       Command(resume=decision_map)
        |                |                    |
        |                |       per-call digest + permission recheck
        |                |                    |
        +----------------+--------------------+
                         |
                ordered ToolMessage list
              (one result per original call ID)
```

### Pattern 1: Single versioned approval projection

**What:** Build a JSON-serializable object with `payload_version`, stable `batch_id`, pending count, and a list of per-call records (`tool_call_id`, tool name, recursively redacted args, capabilities, resource ID/access mode, digest). The projection is for review only; the digest is computed from unredacted canonical arguments [VERIFIED: codebase; CITED: https://docs.langchain.com/oss/python/langgraph/interrupts].

**When to use:** Any batch containing one or more approval-required calls. Call `interrupt()` once for the list, not once per tool call, to honor D-03.

### Pattern 2: Fail-closed resume normalization

**What:** Parse a mapping keyed by `tool_call_id`; accept only explicit boolean approval and a digest matching the independently recomputed digest. Missing, malformed, denied, unknown, or mismatched entries become that call's structured `PermissionDenied` result. Approved entries are the only items submitted to Runtime execution.

**When to use:** Every `Command(resume=...)` return path. Keep decision handling per call so one mismatch cannot cancel unrelated approved calls.

### Pattern 3: Replay-safe direct execution

**What:** Because LangGraph restarts the interrupting node from its beginning [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts], avoid non-idempotent direct tool side effects before the interrupt. Prefer splitting direct execution and approval collection into separate graph nodes, or persist direct results in LangGraph state before entering the approval node. If the adapter keeps one node, it must explicitly detect/reuse a prior state projection and document at-least-once behavior.

**When to use:** Whenever D-01 requires direct calls to complete before pending approvals are surfaced.

### Pattern 4: Ordered result merge

**What:** Keep original input index and ID alongside every immediate result, pending decision and approved execution result. After resume, merge all categories by index and emit exactly one `ToolMessage` per input call. `asyncio.gather` preserves input order while independent failures remain values rather than raised batch exceptions [VERIFIED: codebase].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph checkpoint persistence | Adapter-specific JSON checkpoint or approval store | LangGraph checkpointer + `thread_id` | LangGraph persistence is required for interrupt/resume and owns graph state [CITED: https://docs.langchain.com/oss/python/langgraph/persistence]. |
| Human pause primitive | Event/condition variable or polling loop | Public `langgraph.types.interrupt` | Public API supplies resumable exception and payload delivery [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]. |
| Resume routing | Custom callback or mutable global approval map | `Command(resume=...)` on the same thread | Resume value is delivered to the paused interrupt call [CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]. |
| Capability/digest/redaction | New hash, masking, or policy implementation | `PermissionPolicy`, `redact`, `action_digest` | Existing code already defines canonical fields and recursive masking [VERIFIED: codebase]. |
| Tool execution/retry/locks | Direct `.invoke()` from adapter | `Runtime.execute_explicit_tool` / `execute_explicit_batch` | Preserves timeout, retry, lock, permission and audit boundaries [VERIFIED: codebase]. |

## Common Pitfalls

### Pitfall 1: Re-executing direct side effects on resume

**What goes wrong:** The node runs from its beginning after `Command(resume=...)`, so direct calls placed before `interrupt()` can execute twice [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts].

**How to avoid:** Split direct execution from approval node, use idempotency keys/state projection, and add a test asserting a direct tool invocation count remains one across pause/resume. Do not claim exactly-once.

### Pitfall 2: Holding a resource lock while waiting

**What goes wrong:** A pending approval can hold a lock indefinitely and block unrelated calls.

**How to avoid:** Build approval metadata without acquiring locks; acquire locks only after an item is explicitly approved and revalidated (D-02) [VERIFIED: Phase 9 context and Phase 6 implementation].

### Pitfall 3: Treating redacted arguments as digest input

**What goes wrong:** If the digest hashes `[REDACTED]` instead of original arguments, a secret or changed value may not be bound to approval.

**How to avoid:** Hash canonical unredacted `CallTool.arguments`; use `redact()` only for the interrupt/audit projection [VERIFIED: `permission.py` and redaction tests].

### Pitfall 4: Resume decision keyed by list position

**What goes wrong:** Reordered or missing decisions can approve the wrong call.

**How to avoid:** Key decisions by original `tool_call_id`, bind digest to original index/run ID, and reject duplicate/unknown IDs. Missing IDs default to denial (D-10).

### Pitfall 5: Changing interrupt call order or count

**What goes wrong:** LangGraph associates resume values with interrupt position; changing call order can bind a value to a different interrupt [CITED: https://docs.langchain.com/oss/python/langgraph/backward-compatibility].

**How to avoid:** Use one deterministic interrupt per approval batch, keep payload shape stable, and avoid conditional extra interrupt calls in the same node.

### Pitfall 6: Optional dependency tests silently skip

**What goes wrong:** A broad `importorskip` can hide a broken installed integration.

**How to avoid:** Keep fake/core tests independent; skip real tests only when import fails with a message containing the install hint. In the clean environment where dependencies are present, assert the real StateGraph tests execute (D-16).

### Pitfall 7: Losing `tool_call_id` or leaking exception details

**What goes wrong:** LangGraph cannot correlate results with calls, or raw stack/secret values reach the model.

**How to avoid:** Always construct `ToolMessage(tool_call_id=original_id)` and reuse the existing safe error serializer; test every failure category and redaction marker [VERIFIED: current adapter tests].

## Code Examples

### Public interrupt/resume skeleton

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt

def approval_node(state):
    payload = state["approval_payload"]  # JSON-serializable, redacted
    decisions = interrupt(payload)
    return {"decisions": decisions}

graph = (
    StateGraph(State)
    .add_node("approval", approval_node)
    .add_edge(START, "approval")
    .compile(checkpointer=MemorySaver())
)
config = {"configurable": {"thread_id": "batch-1"}}
paused = graph.invoke({"approval_payload": payload}, config=config)
resumed = graph.invoke(Command(resume=decision_map), config=config)
```

This uses only public APIs and requires the same `thread_id` for resume [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]. The adapter should put actual tool execution after resume and route it through Runtime, not call the LangChain tool directly.

### Digest/projection split

```python
digest = action_digest(action, capabilities=tool.capabilities,
                       run_id=run_id, step=input_index)
review_item = {
    "tool_call_id": call_id,
    "tool_name": action.tool_name,
    "arguments": redact(action.arguments),
    "capabilities": sorted(tool.capabilities),
    "resources": [{"id": rid, "access": access.value}
                  for rid, access in tool.resources.items()],
    "action_digest": digest,
}
```

`redact()` recursively masks sensitive keys while `action_digest()` canonicalizes the original argument mapping [VERIFIED: `src/agentguard/runtime/permission.py`].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Adapter-owned checkpoint/approval file | LangGraph checkpointer + `interrupt`/`Command(resume=...)` | Current public LangGraph docs | One authoritative graph state and framework-native replay [CITED: https://docs.langchain.com/oss/python/langgraph/persistence]. |
| Static breakpoints for user approval | Dynamic `interrupt()` with JSON payload | Current public LangGraph docs | Pause can be conditional on pending calls and carries review data [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]. |
| Hashing display-safe arguments | Digest canonical original arguments; redact only projection | AgentGuard Phase 5 | Prevents approval bypass through secret masking [VERIFIED: codebase]. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The clean-install evidence will continue to use the currently observed `langgraph==0.6.11` and `langchain-core==0.3.86`, or a planner-approved bounded range around them. | Standard Stack | Tests may fail or compatibility promise may be inaccurate. |
| A2 | A LangGraph state projection or separate node can carry direct-call results without adding an AgentGuard checkpoint store. | Pattern 3 | Direct calls could repeat on resume; implementation must prove invocation-count behavior. |

## Open Questions

1. **How should direct-call results be carried across the pause?**
   - What we know: Nodes restart from the beginning; pre-interrupt effects must be idempotent [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts].
   - What's unclear: Whether to split the adapter into two graph nodes or store an internal state projection in one node.
   - Recommendation: Prefer two-node orchestration in the plan; if preserving one `GuardedToolNode` entry point, make the state projection explicit and test duplicate prevention.

2. **What exact version constraint should be published?**
   - What we know: Local metadata is `langgraph 0.6.11` and `langchain-core 0.3.86`; `pyproject.toml` currently allows `<1.0` ranges [VERIFIED: local package metadata; VERIFIED: codebase].
   - What's unclear: Clean environment resolution and whether a lower bound should be tightened.
   - Recommendation: Run clean-install tests, then document only the tested versions/range; do not claim all historical versions.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Adapter/tests | ✓ | 3.12.9 | — |
| `langgraph` | Real interrupt/resume tests | ✓ | 0.6.11 | Skip real tests with install hint if absent |
| `langchain-core` | AI/Tool message types | ✓ | 0.3.86 | Fake-message unit tests remain runnable if absent |
| `pytest` + `pytest-asyncio` | Automated evidence | ✓ | repository environment | — |

Missing dependencies with fallback: `langgraph`/`langchain-core` can be absent for core tests; integration tests must skip explicitly rather than silently pass (D-16).

## Validation Architecture

Validation architecture is intentionally omitted because `.planning/config.json` explicitly sets `workflow.nyquist_validation` to `false`. The phase plan should still add focused pytest tests and run the existing suite as required by COMPAT-04.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no (deferred) | No identity/authentication is introduced in v0.3. |
| V3 Session Management | no (deferred) | LangGraph `thread_id` is a checkpoint pointer, not an authenticated user session. |
| V4 Access Control | yes | Reuse `PermissionPolicy`, fail-closed missing decisions, per-call digest validation. |
| V5 Input Validation | yes | Validate tool call shape, decision DTOs, IDs, capabilities and digest before side effects. |
| V6 Cryptography | yes (narrow) | Use existing SHA-256 `action_digest`; do not invent signing/encryption in this phase. |

### Known Threat Patterns for Python/LangGraph adapter

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Resume payload approves a changed argument | Tampering | Recompute digest from original tool/args/capabilities/run ID/index; reject only mismatched call. |
| Sensitive argument appears in interrupt | Information disclosure | Recursive `redact()` projection and tests for password/token/private-key/authorization keys. |
| Missing decision defaults to allow | Elevation of privilege | Missing or malformed decision is `PermissionDenied`; execute only explicit approval. |
| Duplicate side effect after replay | Repudiation/Tampering | Separate pre-interrupt direct work or use idempotency/state projection; document at-least-once limit. |
| Tool disappears between pause and resume | Tampering/Availability | Resolve tool again; return structured unknown-tool failure for that call, not an unhandled exception. |

## Sources

### Primary (HIGH confidence)

- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — public `interrupt`, checkpointer/thread requirements, `Command(resume=...)`, replay and side-effect rules.
- [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) — `Command(resume=...)` input semantics.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — checkpointer ownership and fault-tolerance model.
- [LangGraph backward compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility) — interrupt/task ordering and replay compatibility warning.
- AgentGuard source and tests (`src/agentguard/integrations/langgraph.py`, `runtime/engine.py`, `runtime/permission.py`, `tests/unit/*`, `tests/integration/*`) — existing execution, redaction, digest and optional-dependency contracts [VERIFIED: codebase].

### Secondary (MEDIUM confidence)

- Existing `.planning/research/SUMMARY.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `STACK.md` — prior milestone synthesis; exact versions were rechecked locally for this phase.

### Tertiary (LOW confidence)

- None used for implementation claims; no unverified community package or API was recommended.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions observed locally and APIs verified against current official docs.
- Architecture: HIGH — ownership and replay behavior are locked by Phase 9 context and official interrupt semantics.
- Pitfalls: HIGH — replay, interrupt ordering and checkpointer requirements are documented by LangGraph; adapter-specific edge cases are covered by repository tests.

**Research date:** 2026-09-03
**Valid until:** 2026-10-03 for stable design claims; dependency versions should be rechecked immediately before release.
