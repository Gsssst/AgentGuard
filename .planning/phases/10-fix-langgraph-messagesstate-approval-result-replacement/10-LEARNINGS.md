# Phase 10 学习记录：修复 MessagesState 审批结果重复

**日期：** 2026-09-04  
**范围：** LangGraph `MessagesState + add_messages` 审批恢复路径

## 1. 目标与边界

本阶段只修复 v0.3 审计发现的 B1 blocker：审批暂停时的占位
`ToolMessage` 与恢复后的最终结果在 `add_messages` reducer 下被追加，导致同一个
`tool_call_id` 出现两条结果。LangGraph 继续拥有 graph state、checkpoint 和
`interrupt/resume` 生命周期；AgentGuard 继续负责工具权限、digest、资源锁、超时、重试和
结构化失败边界。

## 2. 故障复现

原实现的状态序列是：

```text
pause:  [AIMessage, ApprovalRequired(call-1)]
resume: [AIMessage, ApprovalRequired(call-1), success(call-1)]
```

这不是单个工具执行失败，而是 adapter 返回 projection 与 LangGraph reducer 语义不匹配。
Phase 9 的 plain-list 测试通过，但真实 `MessagesState` probe 暴露了该跨阶段问题。

## 3. 设计修复

- **D-01/D-02/D-03：** `prepare()` 在存在 pending approval 时只写固定键
  `_agentguard_prepared`，保存直接结果、pending 调用和 digest 绑定，不返回 `messages`，
  因此不再写入用户可见占位消息。
- **D-04/D-07：** 没有 pending 调用时，`prepare()` 直接返回最终消息；路由只需检查
  `_agentguard_prepared.pending`。
- **D-05/D-06/D-08：** 保留旧 `__call__()`，审批图显式注册 `prepare()` 和 `approval()`，
  不增加 graph-node factory；旧入口的 replay 限制仍按 at-least-once 语义记录。
- **D-09/D-10/D-11/D-12：** `approval()` 恢复后将直接、批准、拒绝、缺失决定、digest
  mismatch、工具缺失和执行失败结果按输入索引合并，一次生成每个原始 ID 的最终消息，并将
  pending 列表标记为空；回归只覆盖默认 `messages` reducer。

## 4. 主动故障与观察

| 故障 | 预期 | 结果 |
|---|---|---|
| 审批暂停时占位消息写入 `messages` | 不应出现 `ApprovalRequired` | 已修复，暂停状态仅保留原始 AIMessage |
| 混合批次含直接、审批、无 guard 调用 | 失败隔离且恢复后保序 | 通过；每个调用各有一条结果 |
| 直接调用在 resume replay | 不应重复副作用 | 通过；计数保持 1 |
| 缺少或篡改 digest | 仅对应调用拒绝 | 通过；其他调用不受影响 |
| 敏感参数进入 interrupt | 只能出现递归脱敏值 | 通过；未暴露原始敏感值 |

## 5. 验证证据

目标回归命令：

```text
PYTHONPATH=src pytest -q tests/integration/test_langgraph_approval.py \
  tests/integration/test_langgraph_optional.py tests/unit/test_langgraph_adapter.py -rs
24 passed
```

完整回归命令：

```text
PYTHONPATH=src pytest -q
```

还需在执行收尾时再次运行 v0.3 milestone audit，确认 B1 以及受影响的
`BATCH-04`、`APPROVAL-03`、`APPROVAL-06` 从 partial 恢复为 fully satisfied。

## 6. 已知限制

- 兼容性证据仍以已验证的 `langgraph 0.6.11`、`langchain-core 0.3.86` 和当前 Python 环境为边界。
- 旧 `__call__()` 的审批路径保留 at-least-once replay 限制，不宣称 exactly-once 外部副作用。
- 本阶段不扩展自定义 `messages_key`、多 reducer、审批 UI、RBAC、外部服务、分布式锁或高可用。

