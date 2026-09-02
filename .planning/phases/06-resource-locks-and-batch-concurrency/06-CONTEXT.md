# Phase 6: Resource Locks and Batch Concurrency - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

为现有本地 Python Agent Runtime 增加进程内资源锁和显式批量并发执行能力。Phase 6 只处理无依赖 Action 的平面批次、读写资源冲突、死锁预防、锁等待超时和结构化结果；不扩展为分布式锁、数据库锁、跨进程调度、DAG 编排或 Router 自动并发决策。

</domain>

<decisions>
## Implementation Decisions

### Resource locking model
- **D-01:** 第一版采用进程内 `ResourceLockManager`。
- **D-02:** 资源访问使用读写锁：多个 `read` 可共享，`write` 和 `destructive` 需要独占。
- **D-03:** 采用写优先策略，避免写操作或 destructive 操作长期饥饿。
- **D-04:** 冲突默认等待，超过 `lock_timeout` 后返回结构化锁超时结果。
- **D-05:** Tool 执行前申请全部资源锁，成功、失败、超时、取消或异常都必须释放。

### Deadlock prevention
- **D-06:** 多资源按确定性的资源 ID 排序后统一获取。
- **D-07:** Tool 必须一次性声明完整资源集合，执行过程中不临时追加锁。
- **D-08:** 获取部分锁后失败时，已获取的锁必须全部释放。
- **D-09:** 第一版不支持 read-to-write 锁升级；需要写入时必须直接声明写模式。

### Resource declaration
- **D-10:** Tool 使用 `resources: Mapping[str, ResourceAccess]` 声明资源和访问模式。
- **D-11:** `ResourceAccess` 固定包含 `read`、`write`、`destructive`。
- **D-12:** 资源名是非空字符串业务 ID，只做首尾空白清理，不自动解析路径、URL 或大小写。
- **D-13:** 资源模式必须被 Tool capability 标签覆盖：read 需要 `read`，write 需要 `write`，destructive 需要 `write` 和 `destructive`。
- **D-14:** 没有资源声明的 Tool 在启用锁管理器时仍可执行，但不参与资源冲突保护；后续再考虑严格声明模式。

### Batch execution
- **D-15:** 新增显式 `execute_batch()` 并发入口，现有 `Runtime.run()` 继续保持顺序兼容。
- **D-16:** 批次只接受彼此独立的平面 Action，不支持依赖关系、DAG 或隐式排序。
- **D-17:** 批次采用 independent 失败语义：每个 Action 独立执行并返回独立结果，一个失败不自动取消其他 Action。
- **D-18:** 多 Runtime 只有在显式注入同一个 `ResourceLockManager` 时才共享锁；未注入时默认创建本地管理器。

### the agent's Discretion
- 具体锁管理器内部数据结构、异步原语、结果 DTO 名称和事件字段顺序。
- 批次结果是否使用 tuple、mapping 或专门的不可变 DTO，只要保留输入关联并保持确定性。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/PROJECT.md` — 本地、学习优先、避免无需求引入分布式基础设施的项目约束。
- `.planning/REQUIREMENTS.md` — v0.2+ 资源锁和读写冲突处理需求。
- `.planning/ROADMAP.md` — Phase 6 的阶段边界和依赖 Phase 5 的关系。
- `.planning/STATE.md` — 当前项目进度和持续性约束。
- `.planning/phases/05-permission-control-and-approval-boundaries/05-CONTEXT.md` — Tool capability、审计、权限边界和副作用前置校验。
- `src/agentguard/runtime/engine.py` — 当前 Runtime 顺序 loop、Tool 调用边界和恢复入口。
- `src/agentguard/runtime/tool.py` — Tool 元数据、ToolRegistry 和统一异步执行入口。
- `src/agentguard/runtime/permission.py` — capability 校验和权限决策模型。
- `src/agentguard/domain/actions.py` — `CallTool` 和 `Finish` Action 约束。
- `src/agentguard/domain/results.py` — ToolResult 和失败类型契约。
- `src/agentguard/events/model.py` — 结构化 Runtime 事件词汇。
- `tests/integration/test_recovery_scenarios.py` — 资源副作用计数和 Runtime 集成测试模式。
- `tests/unit/test_tool_execution.py` — sync/async Tool 的统一执行测试模式。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Tool` / `ToolRegistry`：已有不可变 Tool 元数据边界，适合增加资源声明并在注册时校验。
- `ToolExecutor.execute()`：现有唯一 Tool 副作用边界，资源锁应包围该调用而不是散落在 Tool 内部。
- `Runtime`：已有顺序 Action loop，可保持 `run()` 兼容并增加独立的批量入口。
- `RetryPolicy`、`ToolResult` 和 `RuntimeEvent`：可复用超时、失败归一化和证据记录模式。

### Established Patterns
- 使用 dataclass、`StrEnum` 和 `__post_init__` 在边界处校验。
- 使用异步入口统一 sync/async Tool，不能假设同步函数可被强制取消。
- 所有副作用前先完成输入验证；锁获取失败不能进入 ToolExecutor。
- 通过事件和结构化结果表达超时、失败和取消，不依赖隐藏计数器。

### Integration Points
- `execute_batch()` 在每个 Action 的 ToolExecutor 调用外层获取和释放资源锁。
- 资源锁超时应在 Tool 启动事件之前返回，避免把未执行的 Action 记录成已启动。
- 权限判断、资源声明校验和锁获取的顺序必须保持：先验证元数据，再授权，再获取锁，最后执行 Tool。

</code_context>

<specifics>
## Specific Ideas

- 示例资源声明：`{"config.json": "read"}`、`{"config.json": "write"}`、`{"config.json": "destructive"}`。
- 示例并发批次：读不同资源可以并行；对同一资源的写读、写删必须协调。
- 统一排序获取锁是第一版死锁防护的核心机制。

</specifics>

<deferred>
## Deferred Ideas

- 跨进程或分布式锁，以及 Redis、数据库或远程协调服务。
- Router 自动生成并发计划、Action 依赖图、DAG 和批次内顺序编排。
- 锁升级、租约续期、抢占式取消和复杂公平调度。
- LangGraph/Pi 适配器、外部框架 benchmark 和 Java Control Plane。
- 资源真实语义证明；当前锁只保护 Tool 显式声明的资源。

</deferred>

---

*Phase: 06-resource-locks-and-batch-concurrency*
*Context gathered: 2026-09-02*
