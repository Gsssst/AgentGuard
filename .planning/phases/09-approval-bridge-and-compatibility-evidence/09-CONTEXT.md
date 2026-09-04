# Phase 9: Approval Bridge and Compatibility Evidence - Context

**Gathered:** 2026-09-03
**Status:** Ready for planning

<domain>
## Phase Boundary

把 AgentGuard 已有的 capability 审批、递归脱敏和 action digest 语义桥接到 LangGraph 的公开 `interrupt` / `Command(resume=...)` 生命周期。Phase 9 支持一个多工具批次中的直接调用先执行、多个待审批调用统一中断、按 `tool_call_id` 独立批准或拒绝、恢复时逐调用重新校验 digest，并以原始输入顺序返回完整 `ToolMessage` 结果。同时完成真实/模拟兼容性测试和中英文学习证据。LangGraph 仍是 graph state、checkpoint 和恢复状态的唯一所有者；本阶段不增加 AgentGuard checkpoint 副本、外部审批服务、身份认证、分布式锁或前端审批 UI。

</domain>

<decisions>
## Implementation Decisions

### 审批中断与批次执行
- **D-01:** 一个批次中先执行无需审批的调用，再将所有待审批调用集中到一次 LangGraph `interrupt`；不得让安全调用因其他调用待审批而无条件暂停。
- **D-02:** 待审批调用在中断前不申请或持有资源锁。直接调用完成后构造中断；恢复后，获批调用重新通过 AgentGuard 的权限、资源锁、timeout、retry 和审计边界。
- **D-03:** 一次 `interrupt` 携带待审批调用列表，每项保持独立的 `tool_call_id`、工具和审批绑定信息，审批者可在一次交互中分别决定。
- **D-04:** 直接允许调用即使失败，也只产生自己的结构化结果，不阻止其他调用进入审批中断。

### interrupt 载荷与脱敏
- **D-05:** 每个待审批项只暴露最小但可审计的信息：`tool_call_id`、工具名、递归脱敏的参数摘要、所需 capabilities、资源 ID 与访问模式，以及独立 action digest。
- **D-06:** 参数摘要复用 AgentGuard 现有 `redact()` 规则，包括嵌套对象；不得在 interrupt 载荷中暴露原始密码、token、secret、API key、private key 或 authorization 值。
- **D-07:** 资源摘要展示业务资源 ID 和 `read` / `write` / `destructive` 访问模式，但不暴露锁持有者、等待者、线程或锁对象内部状态。
- **D-08:** 中断载荷增加稳定批次摘要，至少包含 `batch_id`、待审批数量和载荷版本；批次摘要不能替代每个调用自己的 digest。

### Command(resume=...) 与部分批准
- **D-09:** 恢复数据按 `tool_call_id` 映射独立的审批决定；每项可包含 `approved`、`actor`、`reason` 和 `action_digest`，并分别进入审计证据。
- **D-10:** 恢复数据缺少某个待审批调用的决定时，该调用默认拒绝；只执行明确批准的调用，绝不默认放行。
- **D-11:** 部分批准恢复后仍为原始 `tool_calls` 中的每个调用返回一个结果，并严格保持原始输入顺序。拒绝或缺少决定的调用返回结构化 `PermissionDenied`；批准调用返回其实际成功或失败结果。
- **D-12:** 每个待审批调用使用保存的工具名、原始参数、capabilities、`run_id` 和原始调用索引重新计算 digest。单项 digest 不匹配只拒绝该调用，不影响其他调用的校验和执行。

### 兼容性证据与学习记录
- **D-13:** 第一版锁定并记录本地实际验证的 `langgraph` 与 `langchain-core` 版本，完成干净环境可选依赖安装和真实 `StateGraph` interrupt/resume 证据；不宣称支持所有历史版本。
- **D-14:** 故障测试覆盖审批通过、明确拒绝、缺少决定、digest 不匹配、参数篡改、恢复时工具不存在、敏感参数脱敏，以及批准后工具自身执行失败。
- **D-15:** 生成两份结构对应的学习记录：中文和英文各一份，均记录设计选择、主动故障、调试/修复、测试证据和已知限制。
- **D-16:** 未安装 LangGraph 可选依赖时，核心 AgentGuard 测试继续运行，真实集成测试以明确原因和安装提示跳过；依赖已安装时真实集成测试必须执行，不能无故跳过。

### the agent's Discretion
- interrupt payload、resume DTO 和辅助 dataclass 的具体公开名称及 JSON 字段顺序，只要满足上述稳定语义并使用 LangGraph 公共 API。
- 如何在一次 Node 调用内部保存直接调用结果以配合 LangGraph replay 语义，但不得新增第二套持久 checkpoint，也不得让直接调用在恢复重放时产生未声明的重复副作用。
- 当前已验证依赖版本的精确约束表达方式（精确 pin 或有界范围），以干净环境测试证据为准。
- 中英文学习记录的文件名和章节标题，只要两份内容一一对应且均包含主动故障证据。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and milestone scope
- `.planning/PROJECT.md` — v0.3 LangGraph Adapter 目标、LangGraph/AgentGuard 所有权边界和项目诚实性约束。
- `.planning/REQUIREMENTS.md` — APPROVAL-01..06 与 COMPAT-03..05 的验收要求。
- `.planning/ROADMAP.md` — Phase 9 目标、成功标准和 v0.3 收尾范围。
- `.planning/STATE.md` — 当前项目进度和学习/故障证据约束。

### Prior phase decisions and evidence
- `.planning/phases/08-multi-tool-batch-execution/08-CONTEXT.md` — 批量保序、失败隔离、并发上限、资源锁和 Phase 9 审批边界。
- `.planning/phases/08-multi-tool-batch-execution/VERIFICATION.md` — 多工具批量实现与 120 个测试的阶段证据。
- `.planning/phases/07-guardedtoolnode-foundation/07-CONTEXT.md` — GuardedToolNode 输入输出、Adapter-owned registry、Runtime 注入和 LangGraph 所有权。
- `.planning/phases/05-permission-control-and-approval-boundaries/05-CONTEXT.md` — capability 策略、审批生命周期、递归脱敏、事件审计和 digest 绑定语义。
- `.planning/phases/04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra/04-CONTEXT.md` — checkpoint/replay、恢复证据和 at-least-once 限制。

### Milestone research
- `.planning/research/SUMMARY.md` — 使用 LangGraph 公共 `interrupt` 与 `Command(resume=...)` API 的总体建议。
- `.planning/research/ARCHITECTURE.md` — 直接调用与待审批调用分区、LangGraph checkpoint 所有权和恢复架构。
- `.planning/research/PITFALLS.md` — 重复 checkpoint、参数改变后错误恢复、消息 ID 丢失和可选依赖陷阱。
- `.planning/research/STACK.md` — LangGraph/LangChain 公共 API 与版本验证方向。

### Existing implementation and tests
- `src/agentguard/integrations/langgraph.py` — 当前多调用 GuardedToolNode、ToolGuard、输入保序和安全 ToolMessage 转换入口。
- `src/agentguard/runtime/engine.py` — 现有 PermissionPolicy、显式 Tool/批量执行、资源锁、审批失败结果和事件边界。
- `src/agentguard/runtime/permission.py` — `ApprovalDecision`、`redact()`、`action_digest()` 与 canonical digest 实现。
- `src/agentguard/checkpoint/model.py` — AgentGuard 自身审批 checkpoint 契约；Adapter 不应复制其持久化所有权。
- `src/agentguard/events/model.py` — `APPROVAL_REQUESTED`、`APPROVAL_GRANTED`、`APPROVAL_DENIED` 等审计事件。
- `tests/unit/test_langgraph_adapter.py` — fake message/tool、批量保序、安全失败和可选依赖测试模式。
- `tests/integration/test_langgraph_optional.py` — 当前真实 StateGraph 单/多工具 smoke 测试。
- `tests/unit/test_redaction_and_digest.py` — 递归脱敏与 digest 稳定性/变化测试。
- `tests/unit/test_permissions.py` — PermissionPolicy 和 ApprovalDecision 边界测试。

### External API boundary
- LangGraph/LangChain 的精确公共 API 和当前版本必须在 Phase 9 研究/干净环境验证中确认；不得依赖私有模块或声称未经测试的版本范围。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ToolGuard.approval_required` 已存在，但当前批量路径尚未将其桥接到 LangGraph interrupt。
- `PermissionPolicy.decide()` 已产生 allow/deny/approval-required 三态决定，可用于在副作用和资源锁之前分区调用。
- `redact()`、`action_digest()`、`ApprovalDecision` 和审批事件已经提供脱敏、绑定、恢复输入和审计基础。
- `Runtime.execute_explicit_batch()` 已提供获批调用的保序并发执行、资源锁、timeout/retry 和每项失败隔离。

### Established Patterns
- 所有副作用前先校验输入、权限和 digest；审批等待期间不得持有资源锁。
- 失败转换为安全结构化 `ToolMessage`，详细异常保留在 AgentGuard 事件中。
- 输入索引是 digest/event step，`tool_call_id` 是 LangGraph 消息和恢复决定的外部关联键。
- LangGraph checkpoint/replay 可能重新执行 interrupt 前的 Node 代码，设计必须明确处理直接调用的副作用重放风险。

### Integration Points
- `GuardedToolNode.__call__` 需要先规范化调用并分成直接失败、直接执行和待审批三组。
- 对待审批组构造版本化 interrupt payload；`interrupt()` 返回 resume 数据后逐项校验决定与 digest。
- 获批项交给 Runtime 显式批量入口，拒绝/缺失/mismatch 项在原位置生成安全失败消息，然后与 interrupt 前直接调用结果合并保序。
- 真实 LangGraph 测试必须使用 checkpointer 和 `Command(resume=...)`，证明暂停发生在工具调用前、恢复后只执行批准项。

</code_context>

<specifics>
## Specific Ideas

- 示例 resume 形状：`{"call-2": {"approved": true, "action_digest": "sha256:..."}, "call-3": {"approved": false, "reason": "not allowed", "action_digest": "sha256:..."}}`。
- interrupt payload 是审批展示投影，参数使用脱敏值；digest 必须基于未脱敏的规范化原始参数计算，才能真正绑定操作。
- 一个调用 digest mismatch 不应升级成整批失败，必须保留 Phase 8 的失败隔离和输入顺序。
- Phase 9 是 v0.3 的最后一个能力阶段，完成线包含真实安装/运行证据和中英文学习材料，而不仅是 Mock 测试通过。

</specifics>

<deferred>
## Deferred Ideas

- 审批者身份认证、RBAC/ABAC、签名 token、前端审批 UI、外部审批服务和远程通知。
- 多轮保持 pending、部分决定后再次 interrupt；第一版缺失决定直接拒绝。
- 分布式 checkpoint、跨进程锁、exactly-once 副作用和生产级高可用。
- 广泛 LangGraph 历史版本矩阵；第一版只承诺实际验证的有界版本。

</deferred>

---

*Phase: 9-Approval Bridge and Compatibility Evidence*
*Context gathered: 2026-09-03*
