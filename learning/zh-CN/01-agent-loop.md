# Agent Loop：智能体循环

## Problem：问题

在 Agent Runtime 能够控制故障之前，必须先明确两个边界：哪个组件负责提出下一步行动，哪个组件负责执行或拒绝这个行动。

## Why it matters：为什么重要

如果 Action 和 ToolResult 只是没有约束的字典，Runtime 就无法稳定区分“请求调用 Tool”和“请求结束运行”，非法状态甚至可能在产生副作用之后才被发现。

## My first design：我的第一版设计

采用类似 LangGraph 的状态路由思想，但先由 AgentGuard 自己实现最小抽象：

```text
RunState → Router → 一个 Action → Runtime 校验/执行 → ToolResult → RunState
```

第一版只定义两种类型明确的 Action：`CallTool` 和 `Finish`。`RunState` 保存运行 ID、步骤、运行状态、上一次结果，以及有上限的近期历史。

## Alternatives：备选方案

- 固定 Action 列表适合确定性故障场景，但无法表达基于状态的路由。
- 原始字典接近 LLM Tool Calling 输出，但会把校验推迟到更晚的阶段。
- 直接使用 LangGraph `Command` 会在我们理解 Runtime 语义之前，把核心模型绑定到具体框架。

## Failure modes to test next：下一步要测试的故障

- Router 返回不支持的对象。
- Router 请求不存在的 Tool。
- Tool 抛出异常。
- Router 永远不返回 `Finish`。
- 近期历史超过配置上限。

## What broke：实际故障

在 Runtime 集成测试中，构造了一个永远返回 `CallTool("echo", ...)`、从不返回 `Finish` 的 Router。使用 `max_steps=3` 运行后，Runtime 执行了 3 步，并以 `FAILED / STEP_BUDGET_EXCEEDED` 结束，而不是无限运行：

```text
status: failed
stop_reason: step_budget_exceeded
step: 3
```

另一个故障是 Router 返回普通字典而不是 `CallTool` 或 `Finish`。Runtime 将其转换为 `FAILED / INVALID_ACTION`，没有继续执行未知结构。

## Debug process：调试过程

先用成功场景验证 `echo → Finish`，再用不返回 `Finish` 的 Router 验证预算边界。检查最终 `RunResult` 的 `status`、`stop_reason` 和 `final_state.step`，确认终止发生在第 3 次 Tool 执行之后，而不是第 4 次。

## What is verified so far：目前已验证

领域模型和 Runtime 测试已通过，共 18 个测试。测试验证了：Action 值受到约束；Tool 失败结果使用可序列化的错误字段而不是原始异常对象；近期历史有长度上限；同步/异步 Tool 可以使用同一个异步入口；终态 `RunResult` 的状态和停止原因保持一致；步骤预算可以强制终止不结束的 Router。

## Event 记录：结构化运行日志

Runtime 现在会为关键事实产生 Event：`run_started`、`action_proposed`、`tool_started`、`tool_succeeded`、`tool_failed` 和 `run_finished`。测试使用 `InMemoryEventSink` 检查顺序，命令行运行将使用 `JsonlEventSink` 把每个事件写成一行 JSON。

Event 记录“发生过什么”，而 `RunState` 记录 Router 当前做下一步决策所需的信息。Event 不是 Checkpoint：它不能直接保证进程崩溃后可以恢复，但它能帮助我们解释一次运行。

## CLI vertical slice：命令行闭环

当前可以通过下面的命令运行成功场景：

```bash
PYTHONPATH=src python -m agentguard.cli run --output /tmp/agentguard-run.jsonl
```

实际运行结果为 `status: completed` 和 `stop_reason: completed`，JSONL 中包含从 `run_started` 到 `run_finished` 的 6 个有序事件。这个命令不需要外部模型 API、数据库、Redis 或 RabbitMQ。

## What is not solved yet：尚未解决

timeout、retry、cancellation、loop detection 和 checkpoint/resume 尚未实现。当前模型还没有回答事件或未来 checkpoint 应该在 Tool 执行前后哪个时机持久化。

## Interview questions I can now answer：现在可以回答的面试问题

- 为什么要把 Router 决策和 Runtime 执行分开？
- 为什么在 Runtime 边界使用类型明确的 Python 对象，而不是普通字典？
- 为什么 Event 历史和可恢复的 Checkpoint 状态是两个概念？
- 为什么 `RunResult` 同时包含 status 和 stop reason？
