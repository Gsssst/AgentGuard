# Phase 5: Permission Control and Approval Boundaries - Context

**Gathered:** 2026-09-01
**Status:** Ready for planning

<domain>
## Phase Boundary

为现有本地 Python Agent Runtime 增加基于 Tool 能力标签的权限控制和人工审批边界。Phase 5 覆盖 Tool 标签、显式允许策略、直接拒绝、等待审批、审批后显式恢复、参数脱敏审计和 Action 摘要绑定。用户认证、角色系统、分布式审批服务、前端审批 UI、资源锁和框架适配器仍不在本阶段范围内。

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and phase scope
- `.planning/PROJECT.md` — AgentGuard 的核心价值、第一版约束和基础设施排除项。
- `.planning/REQUIREMENTS.md` — v0.2+ 权限、审批和审计相关需求。
- `.planning/ROADMAP.md` — Phase 5 的范围、依赖 Phase 4 的关系以及并发/适配器的后续边界。
- `.planning/STATE.md` — 当前阶段进度和持续性约束。

### Prior recovery and evidence decisions
- `.planning/phases/04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra/04-CONTEXT.md` — checkpoint、显式 resume、事件证据和 at-least-once 语义。
- `.planning/phases/04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra/04-LEARNINGS.md` — Phase 4 的验证结论和可复用模式。
- `.planning/phases/04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra/04-UAT.md` — 恢复、损坏 checkpoint 拒绝和场景评估的验收证据。
- `.planning/phases/03-loop-guard-and-reporting/03-CONTEXT.md` — 事件、RunResult、报告一致性和 bounded Runtime 决策。
- `.planning/phases/03-loop-guard-and-reporting/03-LEARNINGS.md` — Loop Guard 与证据报告的已验证经验。

### Existing Runtime contracts
- `src/agentguard/runtime/engine.py` — 当前 Runtime loop、Tool 调用边界、checkpoint/resume 入口。
- `src/agentguard/runtime/tool.py` — Tool、ToolRegistry、ToolExecutor 以及 timeout/retry 语义。
- `src/agentguard/runtime/policy.py` — 现有 retry policy，可参考策略对象和 fail-closed 风格。
- `src/agentguard/domain/actions.py` — `CallTool` 和 `Finish` Action 约束。
- `src/agentguard/domain/state.py` — `RunState`、状态和有限历史。
- `src/agentguard/checkpoint/model.py` — checkpoint DTO、生命周期和校验异常。
- `src/agentguard/checkpoint/codec.py` — 严格 JSON 编解码边界。
- `src/agentguard/events/model.py` — 结构化事件类型和 JSON 形状。
- `src/agentguard/events/sinks.py` — append-only 内存和 JSONL sink。
- `src/agentguard/reporting/report.py` — 基于事件和终态的证据报告。
- `tests/integration/test_recovery_scenarios.py` — 确定性 Router/Tool 场景和恢复断言。

No external specs — requirements are fully captured in the decisions above and the referenced project/phase documents.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Tool` / `ToolRegistry`：现有 Tool 注册入口，适合增加能力标签和注册期校验。
- `Runtime`：现有单 Action 顺序 loop，适合在 Tool 执行前插入权限决策，并复用 `_finish()`、checkpoint 和 `resume()`。
- `RuntimeEvent` / `EventSink`：现有结构化事件和 JSONL 持久化路径，适合承载审批审计证据。
- `Checkpoint` / codec / store：已有显式恢复和原子本地存储，可保存 pending Action 与审批状态。
- `build_report()`：已有从事件证据推导指标的模式，可扩展权限拒绝、审批等待和审计一致性。

### Established Patterns
- 使用 dataclass 与 `__post_init__` 在边界处校验 Python 对象。
- 通过显式枚举和结构化异常表达可观察的失败类型。
- 使用规范化、确定性的 JSON 表示生成可比较的 Action 摘要。
- 所有副作用前先完成输入验证；恢复和审批都必须遵循 validate-before-side-effect。

### Integration Points
- 权限判断位于 `ACTION_PROPOSED` 之后、`TOOL_STARTED` 之前，确保被拒绝或待审批的 Tool 不会进入 executor。
- 审批请求需要在 checkpoint 中保留待执行 Action，并与现有 `Runtime.resume()` 的恢复轮次和事件序列衔接。
- 审批事件和权限结果应进入 Reliability Report，但不得破坏 Phase 1–4 已有事件字段和报告兼容性。

</code_context>

<specifics>
## Specific Ideas

- 典型标签示例：`read_file -> {read}`、`write_file -> {write}`、`send_email -> {external, write}`、`delete_file -> {write, destructive}`。
- 推荐的审批流程是“暂停—checkpoint—显式 resume”，不是在后台等待或先执行后补审批。
- 审批摘要应绑定规范化参数；参数在审计展示中脱敏，但摘要计算不能因为展示脱敏而失去绑定能力。

</specifics>

<deferred>
## Deferred Ideas

- 角色模型、RBAC/ABAC、用户认证和真实身份授权。
- 外部审批服务、前端审批 UI、多租户策略和远程审批通知。
- 并发执行、资源锁和读写冲突策略（属于 Phase 5 后续切片或独立阶段）。
- LangGraph/Pi 等框架适配器和 Java Control Plane。
- 跨进程、跨机器的审批状态存储与分布式一致性。

</deferred>

---

*Phase: 05-permission-control-and-approval-boundaries*
*Context gathered: 2026-09-01*
