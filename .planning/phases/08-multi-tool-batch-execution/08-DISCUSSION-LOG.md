# Phase 8: Multi-Tool Batch Execution - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-03
**Phase:** 8-Multi-Tool Batch Execution
**Areas discussed:** 批量输入与异常调用、并发上限与调度、结果保序与失败隔离、资源冲突与锁超时映射

---

## 批量输入与异常调用

| Option | Description | Selected |
|--------|-------------|----------|
| 单调用隔离 | 格式错误只生成当前调用失败消息，其他调用继续 | ✓ |
| 整批拒绝 | 一个错误导致整个批次不执行 | |
| 先过滤再执行 | 忽略错误调用，不返回对应消息 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 重复 ID 单调用失败 | 保留输入位置，不自动改 ID | ✓ |
| 整批拒绝 | 重复 ID 视为批次格式错误 | |
| 自动改 ID | 为其中一个调用生成新 ID | |

| Option | Description | Selected |
|--------|-------------|----------|
| 分别返回结构化失败 | 未知工具为 `UnknownTool`，缺少 guard 为 `PermissionDenied` | ✓ |
| 统一批量错误 | 两类问题都拒绝整批 | |
| 缺少 guard 仍执行 | 绕过 fail-closed 配置 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 稳定占位 ID | 使用 `agentguard-invalid-call-<index>` 并标记原始 ID 无效 | ✓ |
| 保留空字符串 | 可能无法被 LangGraph 正确关联 | |
| 不生成 ToolMessage | 只记录事件，调用方收到缺失结果 | |

**User's choice:** 以上四项均选择单调用隔离、分别返回结构化失败和稳定占位 ID。
**Notes:** 每个输入调用必须有一个对应输出，不能因格式错误或重复 ID 静默丢弃其他调用。

## 并发上限与调度

| Option | Description | Selected |
|--------|-------------|----------|
| 可配置 `max_concurrency` | 未设置沿用现有行为，超过上限排队 | ✓ |
| 固定默认上限 | 固定同时执行数量 | |
| 暂不限制 | 完全交给调用方控制 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 每批次独立 | 每次 Node 调用独立计算额度 | ✓ |
| Runtime 全局共享 | 所有批次共享额度 | |
| 每工具单独配置 | 每个工具维护自己的额度 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 初始化时报错 | 必须是正整数，尽早发现配置错误 | ✓ |
| 运行时视为不限 | 容错但可能放大资源消耗 | |
| 运行时钳制为 1 | 悄悄改变调用方配置 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 复用现有超时 | 不新增排队超时，执行后使用 Tool/锁 timeout | ✓ |
| 新增 `queue_timeout` | 排队超时的调用直接失败 | |
| 节点总超时 | 批次超时后统一处理剩余调用 | |

**User's choice:** 增加每批次独立的可配置并发上限，超出时排队；无效值初始化报错，不增加排队超时。
**Notes:** 保持 Phase 6 和 Phase 7 的边界简单可检查。

## 结果保序与失败隔离

| Option | Description | Selected |
|--------|-------------|----------|
| 严格输入顺序 | 始终按原始 tool_calls 顺序返回 | ✓ |
| 完成顺序 | 按工具完成快慢返回 | |
| 成功先失败后 | 改变输入顺序并增加不稳定规则 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 单调用结构化失败 | 捕获未预期异常，其他调用继续 | ✓ |
| 异常冒泡 | 中止节点并丢失其他结果 | |
| 静默吞掉 | 不返回失败消息 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 单调用 `Cancelled` 消息 | 保留位置并尽量完成其他调用 | ✓ |
| 取消整个批次 | 所有调用一起取消 | |
| 不返回结果 | 交给上层处理缺失消息 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 独立捕获后 `gather` | 每个协程先产出结果，再汇总 | ✓ |
| `gather(return_exceptions=True)` | 汇总层统一转换异常 | |
| 串行保险 | 放弃并发收益 | |

**User's choice:** 严格保序、单调用异常/取消隔离，并由每调用协程捕获后再用 `gather` 汇总。
**Notes:** 目标是一个失败不会自动取消无关调用，同时节点仍返回完整结果列表。

## 资源冲突与锁超时映射

| Option | Description | Selected |
|--------|-------------|----------|
| 复用 Phase 6 资源锁 | Adapter 不复制冲突判断 | ✓ |
| Adapter 预检 | 先分组或排序冲突调用 | |
| 冲突直接失败 | 发现同资源就不执行 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 整体失败并释放 | 部分资源获取后超时，释放全部已获锁 | ✓ |
| 部分资源降级执行 | 在不完整保护下运行 | |
| 重试获取 | 直到成功或批次总超时 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 稳定最小信息 | error、failure_kind、提示、attempts，可带资源 ID | ✓ |
| 仅通用错误 | 不带资源 ID | |
| 完整锁状态 | 暴露持有者/等待者等内部信息 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 严格沿用 Phase 6 | 读共享、写互斥、写优先、锁超时隔离 | ✓ |
| 串行无优先级 | 改变已验证语义 | |
| 调用顺序决定 | 不保证写优先 | |

**User's choice:** 完全复用 Phase 6 锁语义；锁超时只影响当前调用，已获锁全部释放；错误消息最小且稳定。
**Notes:** 不在 Adapter 层新增资源冲突模型，避免两套锁规则产生不一致。

## the agent's Discretion

- 内部并发原语、任务调度细节、DTO 名称和 JSON 字段顺序，只要遵守 CONTEXT.md 中的稳定行为约束。

## Deferred Ideas

- Approval `interrupt/resume` 和 digest 校验（Phase 9）。
- DAG/依赖调度、流式进度、全局并发额度、分布式锁和外部审批服务（后续版本）。
