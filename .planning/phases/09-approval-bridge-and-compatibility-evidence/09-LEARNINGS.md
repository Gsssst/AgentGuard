---
phase: 09
phase_name: "approval-bridge-and-compatibility-evidence"
project: "AgentGuard"
generated: "2026-09-04"
language: zh-CN
paired_record: 09-LEARNINGS.en.md
counts:
  decisions: 16
  deliberate_faults: 9
  fixes: 4
  known_limits: 6
---

# Phase 09 学习记录：Approval Bridge and Compatibility Evidence

本记录只总结已经实现并由测试观察到的行为。它不把本地进程内能力包装成分布式、高可用或 exactly-once 保证。英文对应记录见 [09-LEARNINGS.en.md](./09-LEARNINGS.en.md)。

## 1. 阶段目标与责任边界

Phase 9 将 AgentGuard 的 capability policy、递归脱敏、action digest、timeout/retry、resource lock 和审计事件接到 LangGraph 的公开 `interrupt` / `Command(resume=...)` 生命周期。LangGraph 仍独占 graph state、checkpointer 和 `thread_id` 恢复；AgentGuard 只负责工具调用准入、执行和结构化结果（D-13、D-16）。本阶段没有增加外部审批服务、身份/RBAC、远程持久化、分布式锁或前端 UI。

## 2. 设计决策与实际边界

### 2.1 批次分区与单次中断（D-01～D-04）

- 一个批次先执行无需审批的调用，再把待审批调用合并到一次 `interrupt(payload)`（D-01、D-03）。
- 待审批项在暂停前不申请锁；恢复后重新经过 policy、digest、锁、timeout、retry 和 audit 边界（D-02）。
- 直接调用失败只在自己的位置产生结构化失败，不会阻止兄弟调用进入审批（D-04）。
- 为避免恢复时重复直接副作用，真实 StateGraph 使用独立的 `prepare` 和 `approval` 两个节点。把两者塞进同一个 interrupt 节点仍应按 LangGraph 的重放语义谨慎设计。

### 2.2 审批投影、脱敏与绑定（D-05～D-08）

中断载荷包含稳定的 `batch_id`、`pending_count`、`payload_version`，以及每个调用的 `tool_call_id`、工具名、递归脱敏参数摘要、capabilities、业务资源 ID/访问模式和独立 `action_digest`（D-05、D-07、D-08）。摘要复用 `redact()` 的嵌套字段规则；密码、token、secret、API key、private key 和 authorization 值只以 `[REDACTED]` 等标记出现（D-06）。digest 计算使用未脱敏的规范化原始参数，因此脱敏不会削弱防篡改绑定。

### 2.3 恢复、部分批准与保序结果（D-09～D-12）

`Command(resume=...)` 的决定按原始 `tool_call_id` 映射，并可带 `approved`、`actor`、`reason`、`action_digest`（D-09）。缺少决定默认拒绝，绝不默认放行（D-10）。恢复后每个原始调用恰好对应一个按输入顺序排列的 `ToolMessage`；拒绝、缺失、digest mismatch、恢复时工具消失都会成为该调用自己的结构化 `PermissionDenied`/`UnknownTool` 结果（D-11）。digest 使用保存的工具名、原始参数、capabilities、`run_id` 和原始输入索引重新计算；单项不匹配不会取消其他项（D-12）。

### 2.4 兼容性和学习证据（D-13～D-16）

本版只记录本地实际验证的 `langgraph==0.6.11`、`langchain-core==0.3.86` 和 Python 3.12.9，不承诺历史版本矩阵（D-13）。故障矩阵覆盖审批通过/拒绝/缺失、digest 和参数篡改、恢复时缺少工具、脱敏泄漏、timeout、retry 耗尽、锁冲突和批准后工具失败（D-14）。本文件和英文文件章节对应、证据对应（D-15）。没有可选依赖时，相关测试用明确的 `agentguard[langgraph]` 安装提示跳过，核心测试仍可运行；安装后真实测试不能无故跳过（D-16）。

## 3. 主动故障、观察与修复

| 主动故障 | 观察到的结果 | 修复/防线 |
|---|---|---|
| 审批明确通过 | 只有批准的工具执行，结果保留原 ID | resume 决定逐项归一化后交给 Runtime（D-09、D-11） |
| 审批明确拒绝 | 对应位置返回 `PermissionDenied`，兄弟项继续 | fail-closed per-call 结果（D-10、D-11） |
| 缺少某项决定 | 缺失项默认拒绝，不产生工具副作用 | `normalize_resume_decisions()`（D-10） |
| digest 被替换 | 只拒绝被篡改调用，其他批准项仍可执行 | 使用原始参数和输入索引逐项重算（D-12） |
| 恢复前参数被篡改 | digest 不匹配，底层工具调用次数为零 | 保存原始调用并在恢复边界重新校验（D-05、D-12） |
| 恢复时工具从 registry 消失 | 该调用返回 `UnknownTool`，整批不崩溃 | 恢复阶段逐项重新解析工具（D-11、D-14） |
| 嵌套密码出现在参数中 | interrupt JSON 只看到 `[REDACTED]` | 复用递归 `redact()`，不复制原始 secret（D-06） |
| 批准工具 timeout/retry 耗尽/锁冲突/自身异常 | 各自产生结构化 timeout、retry 或 resource-lock failure，兄弟项不被取消 | 继续复用 Runtime 的 timeout、retry、lock、failure isolation 边界（D-02、D-04、D-14） |
| interrupt 节点重放 | 早期单节点思路可能重复直接副作用 | 改为 `prepare → approval` 两节点；真实测试断言 direct tool 调用次数仍为 1（D-01、D-13） |

## 4. 调试过程与关键修复

1. **保留原始输入索引。** 批准子集被压缩后如果重新使用子集位置，digest 会绑定错误调用；因此 Runtime 批量入口接收 `step_indices`，恢复时仍使用原始索引（D-12）。
2. **修复 pytest 收集冲突。** unit/integration 中同名 `test_langgraph_approval.py` 导致 import-file-mismatch；增加最小 `tests/unit/__init__.py` 和 `tests/integration/__init__.py` 包标记，不改变测试语义。
3. **修复可选依赖收集边界。** approval 单元测试不再在无 LangGraph extra 时阻塞核心套件，改用 `pytest.importorskip` 并输出可操作的 `agentguard[langgraph]` 提示（D-16）。
4. **修复恢复副作用重放风险。** 采用 LangGraph 可持久化的 preparation projection 和独立 approval node，而不是依赖 interrupt 前未返回的内存变量；这只证明测试图中的 at-least-once 边界得到控制，不宣称 exactly-once（D-01、D-13）。

## 5. 测试证据

在当前工作区（Python 3.12.9，`langgraph 0.6.11`，`langchain-core 0.3.86`）观察到：

- `PYTHONPATH=src pytest -q tests/unit/test_langgraph_approval.py tests/integration/test_langgraph_approval.py tests/integration/test_langgraph_optional.py` → **14 passed**。
- `PYTHONPATH=src pytest -q` → **132 passed**。
- Plan 09-02 的额外环境验证：真实 approval/optional tests **6 passed**；optional import 被阻断时核心测试 **91 passed, 12 skipped**，skip 原因为 `install agentguard[langgraph] for LangGraph approval integration tests`（D-13、D-16）。

真实 StateGraph 证据使用 `MemorySaver`、固定 `configurable.thread_id`、公开 `Command(resume=...)` 和 `interrupt`：暂停发生在批准工具调用前；恢复后只执行明确批准项；结果按原始 `tool_call_id` 顺序返回；direct tool 不会在该两节点图中重复执行（D-01、D-03、D-09、D-11）。

## 6. 已知限制与后续方向

- **at-least-once，而非 exactly-once：** LangGraph 节点恢复可能重放；只有把副作用隔离到可审计的 preparation/approval 结构并让工具具备幂等性，才能降低风险，当前没有外部事务或幂等键。
- **无身份与 RBAC：** `actor` 是恢复数据中的审计字段，不代表已完成身份认证或授权。
- **无外部审批 UI/服务：** interrupt payload 仍由调用方消费，项目没有远程审批队列或通知系统。
- **无多轮 pending：** 第一版缺少决定直接拒绝，不支持部分决定后再次 interrupt。
- **锁和状态是进程内：** 不提供跨进程锁、分布式 checkpoint 或生产级 HA。
- **兼容性范围有限：** 只对上述实际验证版本和公开 API 组合提供证据，不承诺所有历史 LangGraph/LangChain 版本。

## 7. 决策证据索引（D-01～D-16）

| 决策 | 证据 |
|---|---|
| D-01～D-04 | `tests/unit/test_langgraph_approval.py` 的 prepare/approval、direct failure 和 one-interrupt 测试；真实 StateGraph replay 测试 |
| D-05～D-08 | approval projection 单测、嵌套 redaction 集成测试、稳定 batch metadata 断言 |
| D-09～D-12 | resume normalization、partial approval、digest mismatch、missing-tool 集成测试 |
| D-13 | `09-COMPATIBILITY.md` 的版本、安装和 StateGraph 证据 |
| D-14 | 本记录第 3 节故障矩阵及 09-02 测试总结 |
| D-15 | 本文件与 `09-LEARNINGS.en.md` 的一一对应章节 |
| D-16 | optional import skip 和无 extra 核心套件结果 |

---
*Phase: 09-approval-bridge-and-compatibility-evidence*
*Evidence date: 2026-09-04*
