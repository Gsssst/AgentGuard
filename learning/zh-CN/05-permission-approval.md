# Phase 5：权限控制与人工审批

## 本阶段学到了什么

AgentGuard 为 Tool 增加了四种固定能力标签：`read`、`write`、`external` 和 `destructive`。一个 Tool 可以同时拥有多个标签。注册时会校验标签，空白、非字符串或未知标签会立即失败。

配置 `PermissionPolicy` 后采用 fail-closed 规则：所有标签都在 `allowed` 中才允许执行；如果至少有一个标签需要人工审批，则返回 `approval_required`；没有允许或审批标签时直接拒绝。没有配置策略时，旧的 Runtime 和 ToolExecutor 行为保持不变。

需要审批的 Action 不会调用 Tool。Runtime 将它标记为 `WAITING_APPROVAL`，把 pending Action、能力集合和 action digest 写入 checkpoint，然后等待外部显式调用 `resume()`。恢复前会重新计算摘要并校验审批决定；摘要不匹配、审批缺失或审批拒绝都不会产生 Tool 副作用。审批通过后只执行 checkpoint 中原始的 pending Action，再继续询问 Router。

摘要是对 Tool 名称、规范化原始参数、能力标签、run_id 和 step 的 SHA-256 绑定。审计事件中的参数会递归脱敏，默认覆盖 password、token、secret、api_key、access_key、private_key 和 authorization 等字段名，但摘要计算不会使用脱敏后的值。

## 已验证与未实现

已验证内容包括能力注册校验、三路权限决策、等待 checkpoint round-trip、显式审批恢复、摘要校验、审批前零副作用、事件记录和全量回归测试。当前测试命令为：

```text
PYTHONPATH=src pytest -q
85 passed
```

`actor` 只是调用方提供的审计标签，不是认证后的身份。第一版没有 RBAC、真实认证、审批 UI、远程审批服务、分布式持久化、并发资源锁，也不宣称 exactly-once 或生产级审批基础设施。
