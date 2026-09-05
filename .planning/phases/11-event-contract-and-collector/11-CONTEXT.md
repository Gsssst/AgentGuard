# Phase 11: Event Contract and Collector - Context

**Gathered:** 2026-09-06
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段定义一个稳定、版本化且安全的 `agentguard.event.v1` 事件 envelope，把现有 Runtime 与 LangGraph Adapter 的事件规范化到同一契约，并实现进程内 `EventCollector`。Collector 为每个逻辑运行分配单调递增序号、维护实时运行摘要、隔离无效事件，并为后续 JSONL、REST、SSE 和 React Console 提供唯一事件边界。

本阶段不实现 JSONL 历史文件、FastAPI 路由、SSE、外部 ingestion、React 前端或网页审批；这些分别属于 Phase 12–14 或后续版本。AgentGuard 核心仍不得依赖 FastAPI 或前端依赖。

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and milestone scope
- `.planning/PROJECT.md` — AgentGuard 核心价值、v0.4 Console 目标、学习证据要求及明确的本地单进程边界。
- `.planning/REQUIREMENTS.md` — Phase 11 直接负责的 OBS-03、OBS-04、COMPAT-01，以及后续阶段对事件契约的依赖。
- `.planning/ROADMAP.md` — Phase 11 的目标、成功标准与 Phase 12–14 的范围划分。
- `.planning/STATE.md` — 当前里程碑位置和不引入数据库、消息队列等基础设施的持续约束。

### v0.4 milestone research
- `.planning/research/ARCHITECTURE.md` — 版本化 envelope、Collector 数据流、后续 API/SSE/UI 消费关系和构建顺序。
- `.planning/research/PITFALLS.md` — 持久化前发布、无界队列、原始异常泄漏、时钟混用和本地持久化能力夸大等风险。
- `.planning/research/STACK.md` — FastAPI/SSE、React/Vite、JSONL 的后续技术边界，以及不引入 OpenTelemetry 第二事件模型的原因。
- `.planning/research/SUMMARY.md` — v0.4 总体建议：Collector 分配单调 ID、应用既有脱敏边界并服务于本地可观测工作流。

### Prior phase decisions
- `.planning/phases/10-fix-langgraph-messagesstate-approval-result-replacement/10-CONTEXT.md` — pending/final 消息、恢复行为与原始 `tool_call_id` 的最终语义。
- `.planning/phases/09-approval-bridge-and-compatibility-evidence/09-CONTEXT.md` — 审批、digest、resume、失败隔离和 replay/duplicate 边界。
- `.planning/phases/08-multi-tool-batch-execution/08-CONTEXT.md` — 批量保序、重复/非法外部调用 ID、资源锁和每调用失败隔离。

### Existing implementation and tests
- `src/agentguard/events/model.py` — 当前 `RuntimeEvent`、`EventType`、时间戳与旧外部字典形状。
- `src/agentguard/events/sinks.py` — `EventSink` Protocol、进程内 sink 和 JSONL sink；Collector 应能作为兼容 sink 接入。
- `src/agentguard/runtime/engine.py` — 当前事件产生点、嵌套 `data.sequence`、恢复序号、批量 `run_id`/`batch_id` 混用，以及部分已脱敏/未脱敏 payload。
- `src/agentguard/runtime/tool.py` — attempt、retry、timeout 与原始异常转为 `ToolResult` 的来源边界。
- `src/agentguard/integrations/langgraph.py` — 外部 `tool_call_id`、batch/approval context 和 Adapter-owned Tool 的关联入口。
- `src/agentguard/runtime/permission.py` — 现有递归 `redact()` 规则，可扩展为有界安全预览而不是重新实现第二套脱敏语义。
- `tests/unit/test_event_sinks.py` — 当前事件顺序、JSONL 形状和数据复制测试模式。
- `tests/unit/test_redaction_and_digest.py` — 嵌套敏感字段脱敏与稳定安全边界测试模式。
- `tests/integration/test_recovery_scenarios.py` — checkpoint/resume、`resume_attempt` 和重复可能性证据。
- `tests/integration/test_batch_concurrency.py` — 批次并发、输入顺序和资源冲突事件测试模式。

### External specifications
- No additional external specification is locked for Phase 11. The event contract is defined by the v0.4 requirements and the decisions in this document.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RuntimeEvent` 与 `EventType` 已提供完整的 Runtime 事件词汇和同步 sink 边界；Phase 11 可以通过 normalizer/collector 兼容接收，而不要求调用方采用 Web 层类型。
- `EventSink.emit()` 是现成接入点，`EventCollector` 可直接注入 `Runtime.event_sink`，继续保持 Runtime 与 Console 解耦。
- `redact()` 已递归处理敏感键；可作为安全预览的语义基础，再增加长度、集合大小和深度限制。
- Runtime 已提供 `resume_attempt`、`duplicate_possible`、attempt、failure kind、timeout source 和 approval 事件，可用于稳定 payload，而无需从文本推断状态。

### Established Patterns
- 公共边界使用 dataclass、`StrEnum` 和 `__post_init__` 做 fail-fast 类型校验，并通过 `to_dict()` 输出稳定 JSON 形状。
- Tool 的执行失败转换为结构化 `ToolResult`，Agent-visible 错误使用安全摘要；Collector 应延续同一做法。
- 批量执行保留输入顺序且单调用失败隔离；事件关联也必须保留该语义。
- 兼容声明以实际测试为边界，核心 `import agentguard` 不得因可选 Console 依赖失败。

### Integration Points
- `Runtime._emit()`、`_emit_external()` 和 `_emit_batch_event()` 需要把 `call_id`/`batch_id`/真实 `run_id` 传播到 normalizer 可识别的位置，并停止让嵌套来源序号承担公共排序职责。
- `GuardedToolNode.prepare()` 与 `approval()` 需要把原始 `tool_call_id` 和稳定逻辑 `call_id` 传入 Runtime 事件链，同时保持 Phase 10 的消息唯一性。
- 新 Collector 应位于核心可安装模块中，仅依赖标准库与 AgentGuard 类型；FastAPI adapter 在后续阶段以可选依赖连接。
- 现有 `JsonlEventSink` 是旧格式 sink 和测试资产，不应在 Phase 11 被误当作 Phase 12 的最终历史存储实现。
- Phase 11 测试需要覆盖模型验证、每事件 payload allowlist、安全预览、关联 ID 传播、序号分配、无效事件隔离、终态约束和不完整运行摘要。

</code_context>

<specifics>
## Specific Ideas

- v1 envelope 采用固定、前端友好的顶层形状；在前述最小字段上加入 `call_id`、`batch_id`、Collector 接收时间和 `extensions`，不适用值显式为 `null`。
- `tool_call_id` 是来源证据，不是数据库主键；内部 `call_id` 才负责把一次调用的审批、attempt、retry 和最终结果串联起来。
- `sequence` 表示 Collector 的接受顺序，而不是物理发生时间；控制台可同时展示 `occurred_at`，但不得按它重写历史顺序。
- 无效事件、终态后的迟到事件和契约拒绝应可被开发者发现，但诊断本身不能伪装成普通 Agent 事件或递归触发 Collector。
- 安全预览必须同时覆盖 arguments、成功返回值、异常文本和嵌套集合，而不只是对常见 key 做浅层替换。

</specifics>

<deferred>
## Deferred Ideas

- JSONL append/reload、截断尾行处理和历史恢复 — Phase 12。
- FastAPI run list/detail API 与内置运行启动入口 — Phase 12。
- SSE、`Last-Event-ID`、慢订阅者队列和外部 ingestion 幂等/传输重试 — Phase 13。
- React run list、timeline、event drawer 和浏览器测试 — Phase 14。
- 网页 approve/deny、认证、RBAC、多租户、分布式 event bus、OpenTelemetry 桥接和生产级 HA — v0.4 之后。
- 原始参数、原始返回值或原始异常的 Console 调试开关不会进入 v0.4。

</deferred>

---

*Phase: 11-Event Contract and Collector*
*Context gathered: 2026-09-06*
