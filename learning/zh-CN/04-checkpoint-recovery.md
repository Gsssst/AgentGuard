# Checkpoint 与恢复

## 问题

进程可能在 Tool 执行完成后、checkpoint 写入前崩溃。Runtime 需要从最近一次确认状态恢复，同时诚实表达这一步可能被重复执行。

## 第一版设计

- checkpoint 只保存恢复下一步所需的最小状态：`run_id`、`RunState`、`max_steps`、事件位置、恢复次数和生命周期。
- 每个完整步骤结束后保存：ToolResult 写回、`step` 自增，然后使用临时文件、`flush`、`fsync` 和 `os.replace` 原子替换正式 JSON 文件。
- 通过显式 `Runtime.resume(path, router)` 恢复；普通 `run()` 不扫描旧文件。
- 恢复前完整校验 JSON、schema version、字段和状态不变量。损坏或不兼容时拒绝，绝不执行 Tool。
- 采用 at-least-once 语义。崩溃窗口中的 Action 可能重放，事件使用同一个 `run_id`、递增的 `resume_attempt` 和 `duplicate_possible` 标记。
- 三个场景共用同一 registry：正常完成、崩溃后恢复、损坏 checkpoint 拒绝。

## 实际验证

```text
PYTHONPATH=src pytest -q
69 passed
```

崩溃场景中，Tool 已执行但第二个 checkpoint 尚未写入；恢复后 Tool 被再次执行，最终仍以 `completed` 结束。损坏 checkpoint 场景在 Tool 副作用计数增加前抛出 `CheckpointCorruptError`，原始文件保持不变。

## 权衡与边界

- 本地 JSON 易读、易测试，但不提供分布式协调或完整断电持久性保证。
- at-least-once 比 exactly-once 简单，但非幂等 Tool 可能产生重复副作用；幂等键和去重存储留到后续阶段。
- Scenario Registry 让测试和评估使用同一事实来源，避免两套场景定义漂移。

## 未解决

Exactly-once、自动恢复、checkpoint 清理、进程级强制终止、外部副作用撤销、Redis/数据库存储，以及 token/成本/语义质量指标均未实现。
