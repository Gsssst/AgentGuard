# Phase 11: Event Contract and Collector - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-06
**Phase:** 11-Event Contract and Collector
**Areas discussed:** 事件格式的严格程度、工具调用的关联方式、序号/重复/异常顺序、安全 payload 与运行摘要

---

## 事件格式的严格程度

### Payload 约束

| Option | Description | Selected |
|---|---|---|
| 核心严格 + 分类型约束 | 公共 envelope 严格校验，每种已知事件使用自己的 payload 模型，扩展进入 `extensions` | ✓ |
| 只约束公共字段 | 顶层严格但 payload 继续接受任意字典 | |
| 完全封闭的严格模型 | 所有字段预先声明，任何扩展都直接拒绝 | |

**User's choice:** 核心严格 + 分类型约束。
**Notes:** 在安全性与向后演进之间保留显式扩展通道。

### 无效或未知事件

| Option | Description | Selected |
|---|---|---|
| 事件拒绝，但不拖垮 Agent | 无效事件不进入时间线，记录安全诊断，Collector 不向 Runtime 抛出 | ✓ |
| 直接抛出异常 | 用异常强制生产方修正，但可能中断 Agent | |
| 尽量修正后接收 | 自动填值或转为 unknown，可能掩盖契约错误 | |

**User's choice:** 事件拒绝，但不拖垮 Agent。
**Notes:** 对观测数据 fail closed，对被观测的 Agent fail open。

### Schema 版本

| Option | Description | Selected |
|---|---|---|
| 固定 `agentguard.event.v1` | 当前只接受/产出 v1，不兼容变化新增 v2 | ✓ |
| `1.0.0` 语义版本 | 让消费者处理多个小版本兼容规则 | |
| 暂时不放版本号 | 实现最少，但后续难以安全演进 | |

**User's choice:** 固定 `agentguard.event.v1`。
**Notes:** v1 含义不可静默改变。

### 可空字段形状

| Option | Description | Selected |
|---|---|---|
| 固定顶层结构，使用 `null` | 每种事件具有同一组顶层键，不适用的关联值为 null | ✓ |
| 不适用字段省略 | JSON 更短，但消费者要区分缺失和空值 | |
| 关联字段都放 payload | 顶层最小，但查询和关联必须解析事件特有结构 | |

**User's choice:** 固定顶层结构，使用 `null`。
**Notes:** 后续讨论在固定结构上增加了 `call_id`、`batch_id`、接收时间和 `extensions`。

---

## 工具调用的关联方式

### 内部与外部调用 ID

| Option | Description | Selected |
|---|---|---|
| 内部 `call_id` + 外部 `tool_call_id` | AgentGuard ID 负责唯一关联，框架 ID 原样保留且不假定唯一 | ✓ |
| 只使用 `tool_call_id` | 普通 Runtime 自行生成，但重复外部 ID 会产生歧义 | |
| 不增加调用级 ID | 只以 `run_id + step` 关联 | |

**User's choice:** 内部 `call_id` + 外部 `tool_call_id`。
**Notes:** Phase 8 已证明外部 ID 可能为空、非法或重复。

### 恢复后的 call_id

| Option | Description | Selected |
|---|---|---|
| 逻辑调用保持同一 `call_id` | 重试、审批恢复和 checkpoint 恢复仍属于同一调用 | ✓ |
| 每次实际执行生成新 ID | 每个执行独立，但无法串起逻辑调用 | |
| 重试保持，恢复更新 | 折中但规则不统一 | |

**User's choice:** 逻辑调用保持同一 `call_id`。
**Notes:** 实际执行差异由 attempt、resume attempt 与 duplicate possible 表达。

### 批次标识

| Option | Description | Selected |
|---|---|---|
| 顶层可空 `batch_id` | 批次及其调用共享 batch ID，同时保留真实 run ID | ✓ |
| batch ID 放 payload | 不增加顶层字段，但消费者需要事件特定解析 | |
| 不展示批次关联 | 无法识别同一轮并发调用 | |

**User's choice:** 顶层可空 `batch_id`。
**Notes:** 修正旧 `_emit_batch_event` 将 batch ID 当作 run ID 的含义混用。

### 工具生命周期完整关联

| Option | Description | Selected |
|---|---|---|
| 所有工具事件强制 `call_id` | 提议、审批、attempt、retry 和最终结果全部关联 | ✓ |
| 能获得时才携带 | 兼容简单，但时间线可能断链 | |
| 只在开始/最终结果携带 | 中间审批和重试无法可靠归组 | |

**User's choice:** 所有工具事件强制 `call_id`。
**Notes:** 旧 Runtime 的补齐由内部适配层完成，不要求调用者手工构造。

---

## 序号、重复和异常顺序

### 序号所有权

| Option | Description | Selected |
|---|---|---|
| Collector sequence 唯一权威 | Collector 分配顶层 sequence，来源序号仅供诊断 | ✓ |
| 继续使用 Runtime 序号 | 恢复和多来源可能造成重置或冲突 | |
| 覆盖并丢弃旧序号 | 契约干净，但失去来源诊断证据 | |

**User's choice:** Collector sequence 唯一权威。
**Notes:** 来源序号只允许进入 `extensions.source_sequence`。

### 相同事件去重

| Option | Description | Selected |
|---|---|---|
| 不按内容自动去重 | 每次接收都分配 sequence，保留真实 replay 证据 | ✓ |
| 内容哈希去重 | 可能删除真实的重复副作用 | |
| 来源序号去重 | 来源序号在恢复/多来源下不稳定 | |

**User's choice:** 不按内容自动去重。
**Notes:** 外部传输的显式幂等键推迟到 Phase 13。

### 迟到事件排序

| Option | Description | Selected |
|---|---|---|
| 按 Collector 接收顺序 | sequence 稳定；发生时间和接收时间分别保留 | ✓ |
| 按发生时间重排 | 需要缓冲，迟到事件会改写既有时间线 | |
| 拒绝时间倒退事件 | 并发来源下会丢有效证据 | |

**User's choice:** 按 Collector 接收顺序。
**Notes:** `occurred_at` 不能改变已经分配的 sequence。

### run_id 复用

| Option | Description | Selected |
|---|---|---|
| 终态后不可复用 | 一个 run ID 永远表示一次逻辑运行 | ✓ |
| 允许终态重新打开 | 最终状态、时长和统计会含糊 | |
| Collector 自动加 generation | 保存数据但偷偷改写调用方 ID | |

**User's choice:** 终态后不可复用。
**Notes:** checkpoint 恢复使用原 run ID 和 `resume_started`；新运行必须使用新 ID。

---

## 安全 payload 与运行摘要

### 参数与返回值

| Option | Description | Selected |
|---|---|---|
| 递归脱敏后的有限预览 | 普通字段可调试，敏感字段替换，集合/深度/长度有界 | ✓ |
| 只显示类型和大小 | 最安全但无法验证实际输入输出 | |
| 本地允许原始值 | 调试方便但会污染 JSONL、SSE、截图和 issue | |

**User's choice:** 递归脱敏后的有限预览。
**Notes:** v0.4 不提供关闭脱敏开关，发生裁剪需明确标记。

### 异常信息

| Option | Description | Selected |
|---|---|---|
| 稳定错误类型 + 安全摘要 | 只暴露 allowlist 字段，原始异常和 stack 不进入 envelope | ✓ |
| 脱敏后展示原始消息 | 仍可能泄漏路径、请求内容或未识别秘密 | |
| 原始异常放 extensions | extensions 最终同样进入持久化与 SSE | |

**User's choice:** 稳定错误类型 + 安全摘要。
**Notes:** 详细本地调试信息由使用者自己的日志承担。

### 运行状态机

| Option | Description | Selected |
|---|---|---|
| 五态状态机 | running、waiting approval、completed、failed、cancelled | ✓ |
| 三态状态机 | 简单但无法显示等待审批 | |
| 最后事件即状态 | 细节多但状态频繁且不稳定 | |

**User's choice:** 五态状态机。
**Notes:** 单个工具失败不等于运行失败；只有运行级终止事件能写入最终状态。

### 缺少 run_started

| Option | Description | Selected |
|---|---|---|
| 接收并标记信息不完整 | 建立摘要但不伪造开始时间或时长 | ✓ |
| 拒绝直到收到开始事件 | 中途接入会丢失后续证据 | |
| 暂存等待开始事件 | 需要额外队列、上限和超时策略 | |

**User's choice:** 接收并标记信息不完整。
**Notes:** 记录 `first_observed_at` 和 `incomplete_start=true`；`started_at`、`duration` 保持 null，直到有效开始事件到达。

---

## the agent's Discretion

- 具体 Python 类型、模块拆分和校验辅助函数。
- 每种事件 payload allowlist、事件级 status 映射及安全摘要文案。
- 安全预览的默认深度、长度、集合上限和截断结构。
- 无敏感信息的稳定 `call_id`/`batch_id` 生成与 checkpoint 传播机制。
- Collector 诊断结构、错误计数和进程内索引的合理有界容量。

## Deferred Ideas

- JSONL 与 REST — Phase 12。
- SSE、传输幂等与外部 ingestion — Phase 13。
- React Console — Phase 14。
- UI approve/deny、认证、RBAC、多租户、分布式 event bus 与原始值调试开关 — v0.4 之后或明确不纳入 v0.4。
