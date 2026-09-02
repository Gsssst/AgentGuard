# Phase 6：资源锁与批量并发

## 本阶段学到了什么

AgentGuard 增加了进程内 `ResourceLockManager`。Tool 可以用 `资源 ID -> 访问模式` 声明资源：`read` 使用共享锁，`write` 和 `destructive` 使用独占锁。资源模式必须与 Tool 的 capability 一致；没有声明资源的旧 Tool 保持兼容，但不会获得资源冲突保护。

多个资源按排序后的资源 ID 获取，避免两个 Action 以相反顺序持锁造成死锁。锁等待有超时，部分获取失败时会释放已获取的锁，Tool 成功、失败、超时、取消和异常都通过 finally 释放锁。写者优先，避免写操作长期饥饿；第一版不支持读锁升级为写锁。

`Runtime.execute_batch()` 是显式的并发入口，只接受无依赖的平面 `CallTool`。结果保持输入顺序，一个 Action 失败不会自动取消其他 Action。资源冲突默认等待，超过 `lock_timeout` 后返回结构化失败，且不会产生 `TOOL_STARTED` 或 Tool 副作用。现有 `Runtime.run()` 仍然保持顺序语义。

## 已验证与未实现

已验证读读并行、写互斥、写优先、排序获取、多资源超时清理、取消释放、批次并发、冲突串行和独立失败。测试命令：

```text
PYTHONPATH=src pytest -q
95 passed
```

这里的锁是单进程内存锁，不是分布式锁，也没有回滚、DAG 依赖、Router 自动并发、租约续期或 exactly-once 保证。资源锁只保护 Tool 显式声明的资源。
