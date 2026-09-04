# Phase 10: Fix LangGraph MessagesState approval result replacement - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

修复标准 LangGraph `MessagesState` 配合 `add_messages` reducer 时，审批恢复产生重复 `ToolMessage` 的问题。`prepare()` 只负责规范化调用、执行无需审批的调用并写入机器可读的准备上下文；它不得把审批占位消息写入用户可见的 `messages`。`approval()` 在 interrupt 恢复后一次性合并直接结果、批准结果和拒绝结果，按原始输入顺序为每个 `tool_call_id` 生成且仅生成一条最终 `ToolMessage`。本阶段同时补充真实 `MessagesState + add_messages` 回归证据，并保护无审批路径和旧 `__call__()` 的兼容行为。

本阶段不新增审批服务、前端、RBAC、分布式锁、DAG/依赖调度、自定义 reducer 兼容矩阵或第二套持久化 checkpoint；LangGraph 继续拥有 graph state、checkpoint 和 interrupt/resume 生命周期。

</domain>

<decisions>
## Implementation Decisions

### 准备状态与消息写入
- **D-01:** `prepare()` 与用户可见消息分离。存在待审批调用时，`prepare()` 不返回审批占位 `ToolMessage`；只返回直接调用结果（如有）和 `_agentguard_prepared` 机器状态。
- **D-02:** 使用固定内部 state key `_agentguard_prepared`，不增加重复含义的布尔字段。
- **D-03:** 混合批次在待审批时把直接结果、pending 调用及其原始参数/digest 绑定保存在 `_agentguard_prepared`；不向 `messages` 发射部分结果。恢复后 `approval()` 合并直接结果、批准结果和拒绝结果，一次性输出完整有序消息。
- **D-04:** 没有待审批调用时，`prepare()` 直接返回最终 `messages`，不需要进入 approval node。

### 公开 API 与图路由
- **D-05:** 保留现有 `__call__()` 行为，确保普通调用方不破坏；需要审批且关注 replay 的图由调用方显式组合 `prepare()` → `approval()`。
- **D-06:** 不新增 graph-node factory。`prepare()` 和 `approval()` 作为公开方法直接注册为 LangGraph 节点，路由函数由调用方维护。
- **D-07:** 路由只判断 `_agentguard_prepared.pending` 是否非空；不维护冗余的 `approval_required` 标记。
- **D-08:** 旧 `__call__()` 通过审批时保留现有行为，并在文档中说明 LangGraph replay 下的 at-least-once/重放限制；本阶段不增加 warning 或硬拒绝。

### 回归测试与兼容证据
- **D-09:** 使用真实默认 `MessagesState + add_messages`，构造包含直接允许、需审批和明确拒绝调用的混合批次，验证 pause/resume 全链路。
- **D-10:** 严格断言暂停状态的 `messages` 不含审批占位 `ToolMessage`；恢复状态对每个原始调用恰好有一条 `ToolMessage`，其 `tool_call_id` 和顺序与输入完全一致。
- **D-11:** 本阶段只保护默认 `messages` reducer，不扩展 `messages_key` 或多 reducer 组合的兼容矩阵。
- **D-12:** 增加两个轻量 smoke test：无审批批次由 `prepare()` 直接返回最终消息；旧 `__call__()` 的普通工具调用结果和消息形状保持不变。

### the agent's Discretion
- `_agentguard_prepared` 内部字段的最小 JSON 形状、直接结果序列化方式和节点返回值的具体构造，只要不把占位消息写入 `messages` 并能在 checkpoint/replay 中稳定恢复。
- 如何在 LangGraph 的 reducer 语义下替换/合并消息（包括必要的消息 ID 或返回 projection），以达到每个原始调用单一最终消息的验收标准。
- 真实集成测试使用的轻量 checkpointer、工具 fake 和测试辅助函数，只要不引入新的运行时依赖或改变生产 API。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and milestone scope
- `.planning/PROJECT.md` — v0.3 LangGraph Adapter 的目标、LangGraph/AgentGuard 所有权边界和项目诚实性约束。
- `.planning/REQUIREMENTS.md` — adapter、批量执行、审批桥接和兼容性验收要求。
- `.planning/ROADMAP.md` — Phase 10 的目标、依赖关系和里程碑演进。
- `.planning/STATE.md` — 当前进度、验证证据和工作流状态。

### Audit finding that motivated this phase
- `.planning/v0.3-v0.3-MILESTONE-AUDIT.md` — B1 blocker：`MessagesState + add_messages` 下审批占位与最终 `ToolMessage` 重复。
- `.planning/v0.3-INTEGRATION-AUDIT.md` — 真实集成审计、复现步骤、影响范围和修复验收建议。

### Prior phase decisions and evidence
- `.planning/phases/09-approval-bridge-and-compatibility-evidence/09-CONTEXT.md` — interrupt/resume、批次保序、digest 绑定、失败隔离和 replay 限制。
- `.planning/phases/09-approval-bridge-and-compatibility-evidence/09-RESEARCH.md` — LangGraph 公共 API 与 reducer/replay 风险研究。
- `.planning/phases/09-approval-bridge-and-compatibility-evidence/09-01-SUMMARY.md` — 审批协议与准备/恢复实现证据。
- `.planning/phases/09-approval-bridge-and-compatibility-evidence/09-02-SUMMARY.md` — 真实 LangGraph interrupt/resume 验证证据。
- `.planning/phases/09-approval-bridge-and-compatibility-evidence/09-03-SUMMARY.md` — 兼容性、文档和学习记录证据。
- `.planning/phases/09-approval-bridge-and-compatibility-evidence/VERIFICATION.md` — Phase 9 验收结果及已知限制。
- `.planning/phases/08-multi-tool-batch-execution/08-CONTEXT.md` — 批量保序、并发上限、失败隔离和资源锁约束。
- `.planning/phases/07-guardedtoolnode-foundation/07-CONTEXT.md` — GuardedToolNode 输入输出、Runtime 注入和 Adapter-owned registry 模式。

### Existing implementation and tests
- `src/agentguard/integrations/langgraph.py` — 当前 `GuardedToolNode.prepare()`、`approval()`、`__call__()` 和 ToolMessage 转换入口。
- `src/agentguard/integrations/approval.py` — `ApprovalBatch`、digest 绑定和 fail-closed resume 规范化。
- `src/agentguard/runtime/engine.py` — 显式批量执行、资源锁、timeout/retry 和结构化失败结果。
- `tests/integration/test_langgraph_approval.py` — 现有审批桥接测试及真实集成测试模式。
- `tests/unit/test_langgraph_approval.py` — 审批协议、脱敏、digest 和恢复决定的单元边界。
- `tests/unit/test_langgraph_adapter.py` — GuardedToolNode 批量、失败隔离、保序和旧入口测试。
- `tests/integration/test_langgraph_optional.py` — 可选依赖和真实 `StateGraph` smoke test 模式。

### External API boundary
- 当前验证的 `langgraph` / `langchain-core` 版本与公开 `MessagesState`、`add_messages`、`interrupt`、`Command(resume=...)` API 是本阶段唯一承诺的外部边界；不得依赖私有 reducer 实现或宣称未经测试的版本范围。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GuardedToolNode.prepare()` 已完成调用规范化、直接/待审批分区、批量执行和 approval context 构造，可在不改变权限/锁/timeout/retry 边界的前提下调整返回 projection。
- `GuardedToolNode.approval()` 已能通过 LangGraph `interrupt()` 恢复、逐调用校验 digest，并把批准/拒绝结果按输入索引合并。
- `ApprovalBatch`、`ApprovalItem` 和 `normalize_resume_decisions()` 已提供稳定的审批 payload 与 fail-closed 决策。
- `_result_message()`、`_failure_message()` 和 `_error_content()` 已提供安全结构化 `ToolMessage` 转换。

### Established Patterns
- 所有副作用前先做输入、工具存在性、权限和 digest 校验；审批等待期间不持有资源锁。
- 一个调用的失败只影响其自身；批量结果必须保持原始输入顺序。
- 原始 `tool_call_id` 是消息关联键；未知/非法调用仍需生成安全、可关联的结构化结果。
- LangGraph 是 checkpoint/replay 的唯一所有者，AgentGuard 不复制第二套持久化状态。

### Integration Points
- 需要修改 `GuardedToolNode.prepare()` 的 pending 返回值，消除审批占位消息进入 `MessagesState` 的路径。
- 需要修改 `approval()` 的最终返回 projection，使 `add_messages` 只留下每个调用的一条最终消息，而不是追加到暂停时的占位消息之后。
- 需要在真实 `StateGraph` 测试中覆盖条件路由、checkpointer、`Command(resume=...)` 和混合批次，证明旧路径与新路径都满足消息唯一性。

</code_context>

<specifics>
## Specific Ideas

- 暂停时的状态应只包含原始 AIMessage（以及其他已有上下文），不应包含 `ApprovalRequired` ToolMessage 占位。
- 恢复后消息应形成按输入索引排列的单一结果序列，例如 `[success(call-1), success(call-2), PermissionDenied(call-3)]`，而不是 `[ApprovalRequired(call-2), success(call-2), ...]`。
- 测试以 `tool_call_id` 做一一对应断言，同时验证直接允许、需审批和拒绝调用的混合批次。
- `__call__()` 仍作为便利兼容入口；需要可控 replay 的使用方式由显式 `prepare()` / `approval()` 节点组合承担。

</specifics>

<deferred>
## Deferred Ideas

- 自定义 `messages_key`、多 reducer 或其他 LangGraph state schema 的广泛兼容矩阵。
- 为旧 `__call__()` 审批 replay 增加 warning、硬拒绝或新的持久化去重机制。
- 多轮审批、部分决定后再次 interrupt、人工审批 UI、RBAC/ABAC、外部审批服务和分布式 checkpoint/锁。
- exactly-once 副作用保证及生产级高可用；当前仍明确是 at-least-once 语义边界。

</deferred>

---

*Phase: 10-Fix LangGraph MessagesState approval result replacement*
*Context gathered: 2026-09-04*
