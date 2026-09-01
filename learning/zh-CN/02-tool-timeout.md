# Tool Timeout 与 Retry

## Problem：问题

Agent 调用的 Tool 可能永久不返回、短暂失败，或者在 Runtime 已经停止等待后继续产生副作用。Runtime 必须有界返回，但不能把“停止等待”错误描述为“底层执行一定停止”。

## Why it matters：为什么重要

没有 timeout，整个 Agent Loop 可能永久阻塞；没有 retry safety，响应丢失可能导致邮件、写入或外部资源被重复创建；没有 retry budget，短暂故障可能演变成 retry storm。

## My first design：第一版设计

- Tool timeout 优先于 Runtime 默认 timeout。
- Timeout 作为 `TIMED_OUT` Observation 写回 `RunState`，Router 可以选择 fallback。
- Async Tool 收到协作式 cancellation；Sync Tool 只停止等待，工作线程可能继续执行。
- `FailureKind` 描述这次失败的性质；`RetrySafety` 描述 Tool 是否适合重复执行。
- 只有 `SAFE + TRANSIENT` 才自动重试。
- `max_attempts` 包含第一次执行；默认值为 1。
- 使用确定性指数退避，不启用 jitter。

## What broke：实际故障

### Tool 自己抛出的 TimeoutError 被误报

第一版使用 `except asyncio.TimeoutError` 捕获 deadline。故障测试发现，Python 中 `asyncio.TimeoutError` 和内置 `TimeoutError` 是同一种异常。因此 Tool 主动抛出 `TimeoutError("upstream service timed out")` 时，被错误记录为 AgentGuard deadline 到期。

修复方式是显式创建 Task，用 `asyncio.wait` 判断 deadline 时 Task 是否仍未完成。只有未完成才产生内部 `_RuntimeDeadlineExceeded`；如果 Task 已完成，其内部 `TimeoutError` 保持为普通 `TRANSIENT` Tool 失败。

### 不合作的 Async Tool 可能吞掉 cancellation

Async Tool 可以捕获 `CancelledError` 后继续等待。如果 Runtime 在 cancel 后继续 `await task`，timeout 本身仍可能无限等待。

修复后，Runtime 发出 cancellation，只让出一次事件循环供协作式 Tool 清理；如果 Tool 仍不结束，就分离该 Task 并立即返回 `TIMED_OUT`。这保证 Runtime 有界返回，但也明确承认底层协程可能继续运行。

## Failure modes：故障模式

- Sync Tool timeout 后，旧线程可能继续执行；因此禁止自动 retry，避免新旧调用重叠。
- `UNKNOWN`、`UNSAFE`、`REQUIRES_IDEMPOTENCY_KEY` 在尚无真实幂等键机制时都不会自动 retry。
- `PERMANENT` 错误即使 Tool 是 `SAFE` 也不会 retry。
- Timeout 自动 retry 当前保持关闭，等待更完整的 cancellation 实验。

## Event evidence：事件证据

事件流现在可以区分：

```text
tool_attempt_started
retry_scheduled
tool_attempt_started
tool_succeeded / tool_failed / tool_timed_out
```

事件会记录 attempt、max_attempts、delay、有效 timeout 及其来源。

## Verified：已验证

当前共 43 个测试通过，覆盖分层 timeout、异步 cancellation、同步线程弱保证、不合作协程、异常分类、retry safety、attempt budget、确定性指数退避、retry 事件和 Router fallback。

## Not solved：尚未解决

真正的进程级强制终止、外部副作用撤销、幂等键与去重存储、随机 jitter、checkpoint/recovery 以及并发资源冲突尚未实现。

## Interview questions：现在可以回答的问题

- 为什么 timeout 不等于副作用已经停止？
- 为什么 retry safety 和 failure kind 必须同时判断？
- 为什么同步 Tool timeout 默认不自动 retry？
- `max_attempts` 为什么比 `retry_count` 更不容易产生歧义？
- Runtime retry 和 Router fallback 有什么区别？
