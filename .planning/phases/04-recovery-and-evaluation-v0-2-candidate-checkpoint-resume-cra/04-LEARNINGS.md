---
phase: 04
phase_name: "recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra"
project: "AgentGuard"
generated: "2026-09-01"
counts:
  decisions: 8
  lessons: 6
  patterns: 6
  surprises: 3
missing_artifacts:
  - "04-VERIFICATION.md"
---

# Phase 04 Learnings: Recovery and Evaluation

本文件是 Phase 4 的结构化复盘。每条结论都来自本阶段计划、执行总结或 UAT；英文摘要用于后续简历和面试准备。

## Decisions

### 1. 用最小恢复状态做 checkpoint
Checkpoint 只保存恢复下一步所需的 `RunState` 投影、运行配置、事件位置和恢复元数据，不复制完整事件日志。

**English:** Store the minimum state required to resume, rather than duplicating the full event history.
**Rationale:** 降低存储体积，并保持 checkpoint 与事件证据各司其职。
**Source:** 04-CONTEXT.md; 04-01-PLAN.md

---

### 2. 选择 schema-versioned JSON，拒绝 pickle 和任意对象序列化
Checkpoint 使用显式字段和 `schema_version=1` 编码；缺字段、类型错误、版本不支持和不可 JSON 化的值分别抛出明确异常。

**English:** Use explicit, schema-versioned JSON and reject pickle, `__dict__`, repr, and implicit defaults.
**Rationale:** 文件可审计、可迁移，且恢复前可以严格验证输入，避免把不可信数据直接交给 Runtime。
**Source:** 04-01-PLAN.md; 04-01-SUMMARY.md

---

### 3. 采用同目录临时文件加原子替换
保存流程为临时文件写入、`flush`、`fsync`，最后 `os.replace`；失败时只清理临时文件。

**English:** Persist atomically with same-directory temp files, flush/fsync, and `os.replace`.
**Rationale:** 写入失败不能破坏上一次仍可恢复的正式 checkpoint。
**Source:** 04-01-PLAN.md; 04-01-SUMMARY.md

---

### 4. 恢复必须显式调用 `Runtime.resume()`
`run()` 不扫描目录、不自动恢复旧文件；只有用户明确提供 checkpoint 路径和 Router 时才进入恢复流程。

**English:** Recovery is explicit through `Runtime.resume(path, router)`; normal `run()` never auto-discovers stale checkpoints.
**Rationale:** 避免隐式副作用和错误恢复，调用方可以明确控制恢复边界。
**Source:** 04-CONTEXT.md; 04-02-PLAN.md

---

### 5. 每个完整 Tool 步骤之后写 checkpoint
顺序固定为 Tool 执行完成、`state.record()`、步数递增，然后触发故障注入并保存 checkpoint；终态也更新生命周期。

**English:** Write a checkpoint only after a complete Tool step has been recorded and counted.
**Rationale:** checkpoint 表示“下一步从哪里继续”，而不是表示 Tool 尚未完成的中间状态。
**Source:** 04-02-PLAN.md; 04-02-SUMMARY.md

---

### 6. 第一版明确采用 at-least-once，而不是 exactly-once
Tool 已完成但 checkpoint 尚未写入时崩溃，恢复可能再次执行该 Tool；事件中用 `duplicate_possible` 明确标记。

**English:** V0.2 guarantees observable at-least-once replay, not exactly-once execution.
**Rationale:** 在没有外部幂等键、事务或分布式协调的前提下，exactly-once 既无法证明也不应宣称。
**Source:** 04-CONTEXT.md; 04-02-SUMMARY.md; 04-03-SUMMARY.md

---

### 7. 用事件证据推导恢复指标
报告从事件流和终态 `RunResult` 推导 checkpoint 写入、恢复成功、重复执行、恢复步数和最终状态正确性，不依赖隐藏计数器。

**English:** Derive recovery metrics from event evidence and terminal state, not hidden counters.
**Rationale:** 报告必须可审计；截断或缺失终态证据时应诚实地报告不可确认。
**Source:** 04-02-PLAN.md; 04-03-PLAN.md

---

### 8. 测试和评估共用一个确定性 Scenario Registry
注册表固定提供 clean completion、crash-and-resume、corrupt-checkpoint rejection 三个场景；每次工厂调用都创建全新的可变对象。

**English:** Share one deterministic scenario registry between tests and evaluation, with fresh fixtures per invocation.
**Rationale:** 防止测试定义和评估定义漂移，并保证结果可重复、互不污染。
**Source:** 04-03-PLAN.md; 04-03-SUMMARY.md

---

## Lessons

### 1. “写入 checkpoint”本身也是可观测事件
checkpoint 文件保存时需要为随后产生的 `checkpoint_written` 事件预留事件位置，否则恢复后可能复用序列号。

**English:** Checkpoint persistence must reserve the sequence position of its own write event to keep resumed event order monotonic.
**Context:** 执行中发现保存和事件发出的先后关系会影响恢复后的审计连续性，最终修正为事件位置预留。
**Source:** 04-02-SUMMARY.md（Event-position reservation deviation）

---

### 2. validate-before-side-effect 是恢复安全的核心边界
损坏、缺字段或不兼容版本的 checkpoint 必须在 Router/Tool 调用前拒绝；测试用副作用计数器验证了这一点。

**English:** Validation-before-side-effect is the key safety boundary for recovery.
**Context:** 仅仅“能解析 JSON”并不够，必须先完成完整结构和版本验证。
**Source:** 04-01-PLAN.md; 04-02-SUMMARY.md; 04-UAT.md

---

### 3. 恢复元数据需要区分运行身份和恢复轮次
恢复沿用同一个 `run_id`，同时递增 `resume_attempt`；这样既能关联同一逻辑运行，又能识别重放发生在哪一轮。

**English:** Preserve logical run identity with `run_id` while distinguishing replay rounds with `resume_attempt`.
**Context:** 仅生成新 run_id 会丢失运行连续性，只有计数恢复轮次又无法跨事件关联。
**Source:** 04-02-PLAN.md; 04-03-SUMMARY.md

---

### 4. “超时/崩溃后后台是否仍在执行”决定了恢复语义
同步 Tool 超时或进程崩溃不能自动证明底层副作用已停止，因此恢复必须按可能重复执行来设计和报告。

**English:** A timeout or crash does not prove that an underlying side effect stopped; recovery must assume replay may occur.
**Context:** 这延续了 Phase 2 的同步超时边界，并在 Phase 4 通过 `duplicate_possible` 变成可见证据。
**Source:** 04-02-PLAN.md; 04-03-SUMMARY.md

---

### 5. “可靠性评估”必须限定测量范围
本阶段评估 Runtime 的终止、恢复和证据完整性，不测 token、成本、真实吞吐或模型语义质量。

**English:** Reliability evaluation needs an explicit scope: runtime recovery evidence, not model quality, cost, or production throughput.
**Context:** 限定指标可以避免在没有数据和基准的情况下夸大结论。
**Source:** 04-CONTEXT.md; 04-03-PLAN.md

---

### 6. 端到端场景比孤立单元测试更能证明恢复闭环
三个共享场景同时覆盖正常完成、崩溃窗口重放和损坏输入拒绝；69 个测试全部通过，UAT 4/4 通过。

**English:** End-to-end deterministic scenarios provide stronger evidence of a recovery loop than isolated unit tests alone.
**Context:** registry、runner、事件和 report 组合后，才能验证用户真正关心的闭环行为。
**Source:** 04-03-SUMMARY.md; 04-UAT.md

---

## Patterns

### 1. DTO 投影 + 严格 codec
把领域对象转换为显式、有限字段的 checkpoint DTO，再由 codec 负责 JSON 编解码和错误分类。

**When to use:** 需要持久化内部状态，同时又不希望序列化格式绑定 Python 实现细节时。
**English:** Use an explicit DTO projection and strict codec when persisted state must remain auditable and implementation-independent.
**Source:** 04-01-SUMMARY.md

---

### 2. validate-before-side-effect
恢复流程先加载、解析、校验完整 checkpoint，再发恢复事件、调用 Router 或执行 Tool。

**When to use:** 任何从外部文件、缓存或数据库恢复可执行状态的入口。
**English:** Validate the entire recovery input before emitting side effects or invoking executable dependencies.
**Source:** 04-01-PLAN.md; 04-02-PLAN.md

---

### 3. 单一 Runtime 执行路径
正常运行和恢复运行共享同一个内部 loop，只在入口阶段重建状态和设置恢复元数据。

**When to use:** 新增恢复、重试或回放能力时，避免维护两套容易漂移的执行语义。
**English:** Reuse one internal execution loop for fresh and resumed runs to prevent semantic drift.
**Source:** 04-02-SUMMARY.md

---

### 4. 同目录原子替换
临时文件必须和正式文件处于同一目录，完成 fsync 后用 `os.replace` 提交。

**When to use:** 本地文件作为小型状态存储，且需要在写失败时保留上一版本。
**English:** Same-directory temp + fsync + replace is a reusable local atomic-write pattern.
**Source:** 04-01-PLAN.md

---

### 5. 共享场景工厂
Scenario factory 每次返回新的 Router、ToolExecutor、RunState、sink、路径和副作用计数器。

**When to use:** 测试、演示和评估需要复用相同故障路径，但又必须保证运行隔离时。
**English:** Fresh scenario factories make tests and evaluation reproducible without shared mutable state.
**Source:** 04-03-PLAN.md

---

### 6. 证据驱动报告
从事件序列、恢复元数据和最终状态计算报告；证据不足时将指标置为零、false 或 null，并把 `evidence_consistent` 置为 false。

**When to use:** 运行结果需要被审计、解释或用于面试展示时。
**English:** Evidence-driven reports should refuse to claim success when terminal evidence is missing or inconsistent.
**Source:** 04-02-PLAN.md; 04-03-PLAN.md

---

## Surprises

### 1. 事件顺序比预想中更容易出现恢复边界问题
最初的 checkpoint 事件位置处理会导致恢复后序列号重用，必须额外设计“预留 checkpoint-written 位置”。

**English:** Event ordering at the checkpoint boundary was subtler than expected.
**Impact:** 这是一个小范围实现偏差，已在 Plan 02 中自动修复；最终 69 个测试通过，恢复事件保持可审计顺序。
**Source:** 04-02-SUMMARY.md

---

### 2. 恢复成功并不等于没有重复副作用
crash 场景可以最终完成，但同一个 Tool 可能被再次执行；这不是测试失败，而是 at-least-once 语义下必须显式承认的结果。

**English:** Successful recovery can still include duplicate side effects.
**Impact:** 报告和学习记录必须同时展示 recovery_success 与 duplicate_possible，不能只展示“最终完成”。
**Source:** 04-02-SUMMARY.md; 04-03-SUMMARY.md; 04-UAT.md

---

### 3. 小规模标准库方案已经足以形成完整闭环
仅使用 Python 标准库、JSON、本地文件和确定性故障注入，就完成了 checkpoint、resume、事件、报告和评估闭环，没有引入 Redis、数据库或服务依赖。

**English:** A small standard-library implementation was sufficient to demonstrate a complete, auditable recovery loop.
**Impact:** 第一版更容易阅读、测试和解释；分布式 durability、幂等协调和真实 benchmark 可以留到后续阶段。
**Source:** 04-01-SUMMARY.md; 04-03-SUMMARY.md; 04-CONTEXT.md

---

## Evidence Snapshot

- Automated tests: `PYTHONPATH=src pytest -q` → **69 passed**.
- UAT: **4/4 passed**, 0 issues, 0 pending.
- Verified scenarios: clean completion, crash-and-resume with duplicate evidence, corrupt-checkpoint rejection before side effects.
- Explicit limitations: no exactly-once guarantee, no process-level kill semantics, no distributed durability, and no model-quality/cost claims.
