---
phase: 11
phase_name: event-contract-and-collector
project: AgentGuard
generated: 2026-09-06
language: zh-CN
paired_record: 11-LEARNINGS.en.md
---

# Phase 11 学习记录：Event Contract and Collector

本记录只描述代码与自动化测试已经证明的行为。Phase 11 建立的是进程内、有限保留的可观测边界，不是分布式日志系统、exactly-once 事件总线或生产级高可用平台。英文对应记录见 [11-LEARNINGS.en.md](./11-LEARNINGS.en.md)。

## 1. 问题与阶段边界

v0.3 的 `RuntimeEvent` 是内部兼容事件：CLI、旧 sink、报告和现有测试依赖它的自由 `data` 形状，因此不能为了 Console 直接改写它。Phase 11 在它后面增加严格的 `agentguard.event.v1` normalizer 与 `EventCollector`，把 Runtime 和 LangGraph Adapter 的事实投影到同一安全时间线（D-01～D-05、D-10）。

本阶段只负责事件契约、关联身份、进程内收集和摘要。JSONL v1 历史与 REST 属于 Phase 12，SSE 和外部 ingestion 属于 Phase 13，React Console 与浏览器交互属于 Phase 14；网页审批、认证和 RBAC 更晚实现。

## 2. 设计与实现取舍

### 2.1 严格 v1 envelope（D-01～D-05）

`EventEnvelope` 固定包含 schema、运行与调用关联、Collector 序号、发生/接收时间、事件状态、payload 和 extensions；不适用的关联字段显式为 `null`（D-02、D-03）。23 个 `EventType` 各有明确 payload allowlist，未知字段不会被偷偷塞进 `extensions`；目前 extensions 只允许来源序号（D-01、D-04）。格式错误只进入有限诊断，不进入正常时间线，也不会从 `EventSink.emit()` 抛回 Agent（D-05）。

保留 `RuntimeEvent` 而增加第二边界的代价是同时维护旧事件与 v1 投影；收益是 COMPAT-01 不要求旧调用方一次性迁移，也不让未来 Web 层反向成为核心依赖。

### 2.2 内部与外部调用身份（D-06～D-10）

内部 `call_id` 是逻辑调用主键；外部 `tool_call_id` 只是可空、可重复的来源证据（D-06）。顺序 Runtime 从非敏感的 `run_id + step` 生成稳定 UUID5；LangGraph 在一条 AIMessage 开始时生成一个真实 `batch_id`，再按原始输入索引生成独立 `call_id`。参数、异常、actor 和审批 reason 都不参与 ID 生成。

Runtime 的 attempt/retry callback 闭包复用同一个 correlation；LangGraph `_agentguard_prepared` 保存 `run_id`、`batch_id`、`call_id`、有效外部 ID 和原始索引，批准恢复后复用这些值（D-07～D-10）。非法外部 ID 只用于生成 Agent 可见的本地占位消息，不进入 envelope 的 `tool_call_id`。

### 2.3 Collector 顺序与运行状态（D-11～D-15、D-19～D-21）

来源 `data.sequence` 只保留为 `extensions.source_sequence`；唯一权威顺序是 Collector 在一个短 `threading.Lock` 临界区内完成的“终态检查 → 分配序号 → append → 替换摘要”（D-11、D-12）。内容相同、来源序号重复或发生时间更早的事件仍按接收顺序进入时间线，不做静默去重或回插（D-13、D-14）。

工具失败、超时、拒绝和批次失败都不会自行终止运行；只有 `run_finished` 能产生 completed/failed/cancelled 终态（D-19、D-20）。先收到工具事件时摘要诚实标记 `incomplete_start=true`，不伪造开始时间或 duration；晚到的合法 start 只补齐开始时间（D-21）。终态 run_id 永不复活，新运行必须换 ID（D-15）。

### 2.4 安全预览与有限保留（D-16～D-18）

参数和结果只通过递归、复制隔离且有深度/节点/集合/字符串上限的预览进入 v1。敏感字段名（如 password、token、secret、API key、authorization）在遍历值之前被替换；截断明确标记 `truncated`（D-16）。原始异常消息、stack、checkpoint 路径、loop signature 和审批 reason 被丢弃，失败只保留类型、分类、次数、timeout 元数据与固定摘要（D-18）。v0.4 没有关闭脱敏或显示原始值的开关（D-17）。

重要边界：当前脱敏识别敏感字段名，而不是扫描普通字符串中的任意秘密。调用方若把凭据塞进名为 `value` 的普通字段，系统不会声称能可靠识别它；应使用结构化敏感字段，并继续避免把原始数据送进遥测。

## 3. 主动故障、观察与根因

| 主动故障 | 观察 | 修复或已确认边界 |
|---|---|---|
| 嵌套 secret、深/宽集合、循环、NaN、bytes 与恶意对象 | 浅层 redaction 会泄漏或导致无界/非 JSON 数据 | `_safety.safe_preview()` 先按敏感 key 脱敏，再施加深度、数量、节点和字符串预算；不调用任意对象的 `repr/str`（D-16、D-17） |
| 异常消息放入 token、文件路径和换行 | 旧 `RuntimeEvent.data.error_message` 能携带原文 | normalizer 丢弃 error/stack/path/reason，只生成固定 `safe_summary`；`test_event_contract.py` 和新 LangGraph 测试断言哨兵不存在（D-18） |
| `batch_id` 被当作 `run_id` | 一次逻辑运行会被错误拆成批次运行 | Runtime 与 Adapter 分离真实 run ID 和共享 batch ID；`test_event_correlation.py` 验证两者不同（D-08） |
| retry、审批恢复和 crash replay 重新生成调用身份 | 同一逻辑调用会在 Console 中断裂 | 生产者生成/保存 call ID，attempt、approval、resume 共用它；恢复测试按 call ID 分组（D-06～D-10） |
| 先提交来源序号 99，再提交 1，并重复提交 1 | 如果信任来源序号会重排或丢事件 | Collector 按实际接受顺序分配 1、2、3，来源值只作扩展证据（D-11～D-14） |
| 终态后再次发送 `run_started` | 若遗忘 run 身份可“复活”已完成运行 | 拒绝并记录 `run_already_terminal`；终态身份在 Collector 生命周期内保留（D-15） |
| `max_runs`、事件 deque 和诊断 deque 超限 | 不限制会造成内存增长；静默裁剪会伪装成完整历史 | 新 run 安全拒绝；事件保留范围与总数分别记录，诊断有限（D-05、D-16） |
| normalizer/commit 故意抛出含 secret 的异常，并让 normalizer 重入读 API | 锁内回调会死锁，异常外泄会中断 Agent | 时钟和 normalizer 在锁外执行；`emit()` 捕获 `Exception` 并只保存固定诊断码 |
| LangGraph unknown/missing-guard/approval 分支直接返回 `ToolMessage` | 早退分支在 Collector 中完全不可见 | Adapter 通过 `Runtime.emit_framework_event()` 发出严格安全事实；子批次关闭自己的 batch 边界，由原始 AIMessage 只发一对边界 |
| 新测试把秘密放进普通 `value` 字符串 | 测试发现 key-based 模型不会内容扫描 | 没有虚构“自动识别任意秘密”；测试改用 token/password 字段，并把该限制写入本记录 |

## 4. LangGraph 审批与兼容性证据

`tests/integration/test_langgraph_observability.py` 使用公开 `StateGraph`、`MessagesState`、`MemorySaver`、`Command(resume=...)` 和固定 `configurable.thread_id`。直接/待审批混合批次在暂停前只有 `batch_started`，恢复完成后才有唯一 `batch_finished`；直接工具调用次数始终为 1，待审批调用只在明确批准后执行。最终每个原始输入按顺序只产生一个 `ToolMessage`，有效 `tool_call_id` 保持不变。

未知工具、重复或非法外部 ID、非法参数、缺 guard、缺决定、明确拒绝、digest mismatch、恢复时工具缺失、transient retry、timeout、批准后失败与 sibling isolation 由新旧 LangGraph 测试共同覆盖。Adapter 事件仍只描述事实；权限、digest、锁、timeout 和 retry 控制始终由 Runtime 执行，不会因可观测接入而绕过（T-11-14～T-11-18）。

核心 `import agentguard` 不会加载 LangGraph、LangChain Core、FastAPI 或未来 Console 模块。可选集成缺失时相关测试以 `agentguard[langgraph]` 提示跳过；本次安装环境只证明 Python 3.12.9、`langgraph==0.6.11` 与 `langchain-core==0.3.86`。

## 5. 可复现测试证据

2026-09-06 在当前工作树观察到：

- `PYTHONPATH=src python -m pytest -q tests/integration/test_langgraph_observability.py tests/integration/test_langgraph_approval.py tests/integration/test_langgraph_optional.py -rs -x` → **12 passed，1 个第三方 deprecation warning**。
- `PYTHONPATH=src python -m pytest -q` → **212 passed**。
- `PYTHONPATH=src python -c "import agentguard"` → 退出码 0。
- `git diff --check` → 退出码 0。

对应的基础证据还包括 `tests/unit/test_event_contract.py` 的 23 种事件矩阵、`tests/unit/test_event_collector.py` 的并发/状态/容量/故障隔离测试，以及 `tests/integration/test_event_correlation.py` 的 retry、审批与 checkpoint 恢复关联测试。

## 6. 安全边界与能力限制

- **进程内：** Collector、锁和索引只在当前 Python 进程中有效，不提供跨进程排序、共享锁或 HA。
- **at-least-once：** 相同有效事实每次到达都会留下证据；不承诺 exactly-once，也不进行内容哈希去重。
- **有限保留：** 每 run 事件、run 数量和诊断都有上限；当前时间线可能只保留尾部，摘要会报告真实总数与保留区间。
- **安全优先：** 没有 raw exception、raw stack 或“关闭脱敏”的 debug 开关；固定摘要会牺牲部分调试细节。
- **版本有限：** 只证明当前固定 LangGraph/LangChain 版本与公开 API，不宣称广泛框架/历史版本兼容。
- **尚未实现：** JSONL/REST（Phase 12）、SSE/外部 ingestion（Phase 13）、React 监管 UI（Phase 14）均不属于本阶段；网页审批控制、认证/RBAC 与多租户更不属于 v0.4 当前切片。

## 7. 决策证据索引（D-01～D-21）

| 决策 | 证据 |
|---|---|
| D-01～D-05 | `test_event_contract.py` 的严格形状/allowlist 拒绝；`test_event_collector.py` 的 fail-open 诊断 |
| D-06～D-10 | `test_event_correlation.py` 与 `test_langgraph_observability.py` 的 call/run/batch 身份和恢复分组 |
| D-11～D-15 | Collector 并发连续序号、来源逆序/重复、终态复用拒绝测试 |
| D-16～D-18 | 安全预览 adversarial tests、错误哨兵与 core-import 隔离测试 |
| D-19～D-21 | 工具失败非终态、审批状态转换、不完整开始与晚到 start 测试 |

---
*Phase: 11-event-contract-and-collector*
*Evidence date: 2026-09-06*
