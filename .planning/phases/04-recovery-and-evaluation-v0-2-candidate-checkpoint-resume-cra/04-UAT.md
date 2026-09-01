---
status: complete
phase: 04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md]
started: 2026-09-01T00:00:00+08:00
updated: 2026-09-01T20:16:00+08:00
---

## Current Test

[testing complete]

## Tests

### 1. 三场景评估入口
expected: run_all 依次运行三个注册场景并返回可 JSON 序列化结果。
result: pass

### 2. 正常运行的 checkpoint 生命周期
expected: clean 场景完成后生成 JSON checkpoint，状态为 completed，且最终状态正确。
result: pass

### 3. 崩溃后的显式恢复
expected: crash 场景在 checkpoint 前崩溃，显式 resume 后完成；沿用同一 run_id，resume_attempt 为 1，并标记可能重复执行。
result: pass

### 4. 损坏 checkpoint 安全拒绝
expected: corrupt 场景在任何 Tool 副作用前拒绝恢复，返回 CheckpointCorruptError，原始文件保持不变。
result: pass

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
