# Phase 8: Multi-Tool Batch Execution - Context

**Gathered:** 2026-09-03
**Status:** Ready for planning

<domain>
## Phase Boundary

扩展 `GuardedToolNode`，使其能够处理单条 `AIMessage` 中的多个 `tool_calls`。本阶段复用 Phase 6 的显式批量并发和进程内资源锁语义，支持独立调用并发、冲突协调、失败隔离、输入顺序结果聚合，以及安全的结构化 `ToolMessage` 错误。LangGraph 继续拥有 graph state、routing 和 checkpoint；审批 `interrupt/resume`、digest-bound 决策属于 Phase 9，不在本阶段实现。

</domain>

<decisions>
## Implementation Decisions

### 批量输入与异常调用
- **D-01:** 批量采用单调用隔离语义。某个调用缺少 `name`、`args` 格式错误或其他输入不合法时，只为该调用生成结构化失败消息，其余合法调用继续执行。
- **D-02:** 重复 `tool_call_id` 不导致整批拒绝，也不自动改写 ID；重复调用保留各自输入位置并分别返回自己的结构化结果/错误。
- **D-03:** 未知工具返回 `UnknownTool` 结构化失败；没有 `ToolGuard` 的已知工具返回 `PermissionDenied`。两者都不得调用底层工具，且不影响同批次其他调用。
- **D-04:** 空或非字符串 `tool_call_id` 使用稳定的本地占位 ID（例如 `agentguard-invalid-call-<index>`），并在消息内容中标记原始 ID 无效；仍然返回一个 `ToolMessage`。
- **D-05:** 每个输入调用都必须对应一个输出消息，不得静默过滤或丢弃异常调用。

### 并发上限与调度
- **D-06:** `GuardedToolNode` 增加可选的正整数 `max_concurrency`。未设置时沿用现有批量并发行为；设置后超出额度的调用排队等待执行槽位。
- **D-07:** 并发上限按一次 `GuardedToolNode` 调用（即当前 `AIMessage` 批次）独立计算，不与其他节点调用或 Runtime 全局额度共享。
- **D-08:** `max_concurrency` 为 `0`、负数、浮点数、字符串或其他非正整数时，在节点初始化阶段立即报配置错误。
- **D-09:** 第一版不新增批次排队超时。调用获得执行槽位后继续受 Tool 自身 timeout 和已有资源锁 timeout 控制；排队仅受调用方/图生命周期约束。

### 结果保序与失败隔离
- **D-10:** 返回的 `ToolMessage` 始终严格按照原始 `tool_calls` 输入顺序排列，无论实际完成顺序如何。
- **D-11:** 每个调用在独立执行协程中捕获工具异常、参数转换异常和适配器内部未预期异常，并转换为该调用自己的安全结构化失败结果；不让单个异常冒泡取消整个节点。
- **D-12:** 单个调用被取消时，为其返回自己的 `Cancelled` 结构化消息，并尽量让其他未取消调用完成。
- **D-13:** 批量汇总采用“每调用独立产出 `ToolResult`，再用 `gather` 汇总”的语义；汇总阶段保留输入索引和原始调用 ID。

### 资源冲突与锁超时映射
- **D-14:** Adapter 层不复制或预检资源冲突，完全复用 Phase 6 的 `ResourceLockManager` 和 Runtime 执行边界。
- **D-15:** 每个调用在执行前申请其声明的全部资源；部分资源已获取而后续资源锁等待超时，则整个调用失败，已获取资源全部释放，底层工具绝不执行。
- **D-16:** 同一资源的访问兼容性严格沿用 Phase 6：多个 `read` 可共享；`write`/`destructive` 与任何访问互斥；写优先；超过 `lock_timeout` 只使当前调用失败。
- **D-17:** 锁超时转换为安全、稳定且最小的结构化消息，至少包含 `error`、`failure_kind=resource_lock_timeout`、安全提示和 `attempts=0`，可附带发生超时的资源 ID；不得暴露锁对象、持有者/等待者状态、线程信息或异常堆栈。

### the agent's Discretion
- `max_concurrency` 信号量或等价排队原语的内部实现，以及批次任务的创建顺序。
- 输入校验错误的具体 `error` 字段命名、消息 JSON 字段顺序和安全摘要措辞，只要每个调用有稳定占位 ID、可区分失败类别且不泄露敏感参数。
- 是否通过显式 Tool 批量执行 seam 扩展 Runtime，以便 Adapter-owned Tool 继续不写入 Runtime 全局 registry；不得绕过 Runtime 的权限、超时、重试、锁和审计边界。
- 对外暴露的辅助 DTO/私有函数名称，以及支持的 LangChain/LangGraph 小版本范围。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and milestone scope
- `.planning/PROJECT.md` — AgentGuard 核心价值、学习优先约束、v0.3 LangGraph Adapter 目标和不夸大能力的边界。
- `.planning/REQUIREMENTS.md` — BATCH-01 至 BATCH-05 的验收要求，以及 Phase 9 审批桥接的明确边界。
- `.planning/ROADMAP.md` — Phase 8 目标、成功标准、依赖 Phase 7 和后续 Phase 9 的范围划分。
- `.planning/STATE.md` — 当前阶段位置和持续性约束。

### Prior phase decisions
- `.planning/phases/07-guardedtoolnode-foundation/07-CONTEXT.md` — `GuardedToolNode` 输入/输出形状、Adapter-owned registry、Runtime 注入、错误消息和单调用边界。
- `.planning/phases/06-resource-locks-and-batch-concurrency/06-CONTEXT.md` — 进程内读写锁、写优先、确定性资源排序、锁超时、显式批量并发和失败隔离语义。
- `.planning/phases/05-permission-control-and-approval-boundaries/05-CONTEXT.md` — capability、fail-closed 权限、审计脱敏和 Phase 9 审批绑定边界。

### Existing implementation and tests
- `src/agentguard/integrations/langgraph.py` — 当前单调用 `GuardedToolNode`、`ToolGuard`、ToolMessage 错误转换和 LangChain async/sync 调用适配。
- `src/agentguard/runtime/engine.py` — `execute_explicit_tool()`、现有 `execute_batch()`、权限/资源锁/事件边界；可能需要增加显式 Tool 批量 seam。
- `src/agentguard/runtime/tool.py` — Tool/ToolExecutor 的统一 async 执行、timeout、retry、失败归一化和事件回调。
- `src/agentguard/runtime/resources.py` — `ResourceLockManager` 的读写兼容、写优先、确定性资源获取和完整释放。
- `src/agentguard/domain/actions.py` — `CallTool` 参数契约和输入校验。
- `src/agentguard/domain/results.py` — `ToolResult`、`FailureKind`、状态和 attempts 契约。
- `src/agentguard/events/model.py` — 工具执行、失败和资源锁超时事件词汇。
- `tests/unit/test_langgraph_adapter.py` — Adapter fake message/tool 测试模式和安全 ToolMessage 断言。
- `tests/integration/test_batch_concurrency.py` — 非冲突并行、资源冲突串行、失败隔离和锁超时测试模式。

### External specifications
- No additional external specs. LangGraph/LangChain API usage is bounded by the existing Phase 7 adapter and its optional dependency tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GuardedToolNode` 已有最后一条 tool-calling `AIMessage` 选择、`ToolGuard` 到 AgentGuard `Tool` 的转换、run ID 读取和安全 `ToolMessage` 构造，可在其单调用分支上扩展批量路径。
- `Runtime.execute_explicit_tool()` 是 Adapter-owned Tool 的权限、锁、timeout、retry 和审计边界；批量实现应复用或提取其单调用逻辑。
- `Runtime.execute_batch()` 已提供输入顺序结果、独立失败和资源锁协调的基础，但当前只从 Runtime registry 查找 Tool，可能需要显式 Tool 批量入口。
- `ToolExecutor.execute_explicit()` 统一处理 async `.ainvoke()` 与 sync `.invoke()` 线程回退、超时、重试和 `ToolResult` 失败类型。

### Established Patterns
- 使用 dataclass、枚举和 `__post_init__` 做边界配置校验；无效的 `max_concurrency` 应遵循同样的 fail-fast 风格。
- 用结构化 `ToolResult` 和安全摘要表达失败，不把底层异常堆栈或敏感参数直接返回给 Agent。
- 资源锁在工具副作用前获取，成功/失败/超时/取消都释放；资源冲突不在 Adapter 层复制判断。
- `asyncio` 批量任务需要显式保存输入索引或依赖 `gather` 的输入顺序保证，确保完成顺序不会影响输出顺序。

### Integration Points
- `GuardedToolNode.__call__` 在找到最后一条 AIMessage 后，将多个调用逐一规范化为批量项，再统一转换为 `ToolMessage` 列表。
- 对无效调用、未知工具、缺少 guard 的早期失败项，需要与可执行项一起进入同一结果聚合流程，以保留输入位置和每调用独立失败语义。
- 每个批次的 `max_concurrency` 信号量应位于 Node 调用内部；Runtime 共享的 `ResourceLockManager` 仍负责跨调用的资源冲突。
- Phase 9 将在此批量结果边界上增加 approval interrupt/resume；Phase 8 不应改变 LangGraph checkpoint 或中断所有权。

</code_context>

<specifics>
## Specific Ideas

- 典型批次可能以 `call-3 → call-1 → call-2` 的完成顺序结束，但返回必须仍是 `call-1, call-2, call-3` 的输入顺序。
- 空或非法调用 ID 的占位形式建议为 `agentguard-invalid-call-<index>`，其中 index 来自原始批次位置，保证稳定且可诊断。
- 锁超时对 Agent 只提供最小稳定信息；详细异常仍留在 AgentGuard 事件/报告中。
- 本阶段的批量入口不能提前引入审批等待；approval-required 调用的 interrupt/resume 属于 Phase 9。

</specifics>

<deferred>
## Deferred Ideas

- LangGraph `interrupt/resume` 审批桥接、独立 approve/reject、digest 重算和 checkpoint 恢复 — Phase 9。
- 基于工具依赖关系的 DAG/拓扑调度、流式进度和跨批次全局并发额度 — 后续版本。
- 分布式/跨进程资源锁、外部审批服务、多租户授权和生产 HA — 不属于当前 v0.3。

</deferred>

---

*Phase: 8-Multi-Tool Batch Execution*
*Context gathered: 2026-09-03*
