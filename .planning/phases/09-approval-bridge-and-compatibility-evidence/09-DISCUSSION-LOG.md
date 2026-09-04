# Phase 9: Approval Bridge and Compatibility Evidence - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-03
**Phase:** 9-Approval Bridge and Compatibility Evidence
**Areas discussed:** 审批中断与批次行为、interrupt 载荷、Command(resume=...) 与部分批准、兼容性证据与学习记录

---

## 审批中断与批次行为

| Decision | Alternatives considered | Selected |
|---|---|---|
| 先执行无需审批调用，再统一中断待审批列表 | 整批先中断；每项单独中断 | ✓ |
| 审批等待期间不持锁，恢复后重新走锁流程 | 中断时持锁；冲突直接拒绝 | ✓ |
| 一次 interrupt 携带独立审批项列表 | 聚合摘要；逐项 interrupt | ✓ |
| 直接调用失败仍继续进入审批 | 失败后整批停止；全部成功才审批 | ✓ |

**User's choice:** 四项均选择推荐的失败隔离与单次列表中断方案。
**Notes:** 安全调用不应因审批调用阻塞；等待人工决定时不能长期占有资源锁。

## interrupt 载荷

| Decision | Alternatives considered | Selected |
|---|---|---|
| 每项包含调用 ID、工具、脱敏参数、能力、资源和 digest | 只显示工具/digest；完整原始参数 | ✓ |
| 复用递归 `redact()` | 仅顶层脱敏；全部隐藏参数 | ✓ |
| 展示资源 ID 与访问模式 | 仅资源数量；完整锁状态 | ✓ |
| 包含 batch_id、数量和载荷版本 | 无批次字段；只有批次 digest | ✓ |

**User's choice:** 使用最小但可审计、版本化且逐调用绑定的载荷。
**Notes:** 批次摘要不能取代每项 digest，展示投影不得泄露原始敏感参数。

## Command(resume=...) 与部分批准

| Decision | Alternatives considered | Selected |
|---|---|---|
| 按 tool_call_id 映射独立决定 | 全局布尔值；决定列表 | ✓ |
| 缺少决定默认拒绝 | 整批报错；继续 pending | ✓ |
| 返回完整且按原始顺序排列的结果 | 只返回批准项；省略失败/拒绝 | ✓ |
| 每项独立重算并校验 digest | 只校验批次；任一 mismatch 拒绝整批 | ✓ |

**User's choice:** 只执行明确批准且 digest 匹配的调用，其他调用返回自己的结构化拒绝结果。
**Notes:** 单项 mismatch 不影响其他项，延续 Phase 8 的失败隔离。

## 兼容性证据与学习记录

| Decision | Alternatives considered | Selected |
|---|---|---|
| 锁定当前验证版本并做干净安装/真实图证据 | 小版本矩阵；只做 Mock | ✓ |
| 覆盖完整审批安全故障链路 | 只测批准/拒绝；只测 mismatch | ✓ |
| 中文、英文各一份对应学习文档 | 单文件双语；中文详英文简 | ✓ |
| 缺依赖明确跳过，装依赖后真实测试必须执行 | 整套失败；始终只测 Mock | ✓ |

**User's choice:** 以实际验证版本、真实 StateGraph 和完整故障证据作为 v0.3 完成标准。
**Notes:** 不夸大兼容范围；两份学习文档都必须记录设计、故障、修复、证据与限制。

## the agent's Discretion

- DTO/字段具体命名、版本约束表达、学习文档文件名和内部 replay 防重复实现方式，在不改变 CONTEXT.md 行为约束的前提下由研究与规划决定。

## Deferred Ideas

- 外部审批系统、身份认证、审批 UI、多轮保持 pending、分布式状态和广泛历史版本矩阵。
