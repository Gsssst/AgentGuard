---
status: complete
phase: 05-permission-control-and-approval-boundaries
source:
  - 05-01-SUMMARY.md
  - 05-02-SUMMARY.md
  - 05-03-SUMMARY.md
started: 2026-09-01T00:00:00+08:00
updated: 2026-09-02T00:10:00+08:00
---

## Current Test

number: 5
name: 审计脱敏与可靠性报告
expected: |
  审批和权限事件应包含 Tool、能力、digest 等结构化上下文；password、token、secret 等敏感字段递归显示为 `[REDACTED]`；ReliabilityReport 能统计权限拒绝、审批请求、通过和拒绝。
awaiting: none

## Tests

### 1. Tool 能力标签注册
expected: 创建合法标签的 Tool 成功并暴露不可变能力集合；非法标签注册失败。
result: pass

### 2. 直接允许与直接拒绝
expected: `allowed={"read"}` 允许 read Tool；write Tool 被拒绝且不会产生 Tool 副作用；未配置策略的旧调用仍可执行。
result: pass

### 3. 审批暂停与 checkpoint
expected: approval-required Tool 首次运行返回 `WAITING_APPROVAL`，写入 pending Action 和 digest 的 checkpoint，审批前副作用为零。
result: pass

### 4. 显式审批恢复与 digest 绑定
expected: 使用匹配 digest 的批准决定恢复时执行原始 pending Action；缺少决定、拒绝或 digest 不匹配时不执行 Tool。
result: pass

### 5. 审计脱敏与可靠性报告
expected: 审批/权限事件包含结构化上下文，敏感参数递归显示为 `[REDACTED]`，报告能统计权限拒绝、审批请求、通过和拒绝。
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

none yet
