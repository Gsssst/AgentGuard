# Phase 7 学习记录：LangGraph Adapter

本阶段实现了 `GuardedToolNode` 的基础适配：LangGraph 负责图状态和 checkpoint，AgentGuard 负责工具权限、超时、重试、资源锁和审计。Adapter 使用自己的工具注册表，并通过 `Runtime.execute_explicit_tool()` 执行，不修改 Runtime 的全局 registry。

## 故障实验

- 未配置 `ToolGuard` 时，底层工具不会被调用，节点返回结构化拒绝消息。
- 缺少消息或 tool call 时，节点返回结构化失败消息，而不是抛出未处理异常。
- 同步工具使用线程回退，异步工具优先使用 `ainvoke()`。
- `ToolMessage` 保留原始 `tool_call_id`；非字符串结果使用稳定 JSON 序列化。

## 验证证据

- `PYTHONPATH=src pytest -q tests/unit/test_runtime_explicit_tool.py`：4 passed。
- `PYTHONPATH=src pytest -q tests/unit/test_langgraph_adapter.py`：4 passed。
- 安装 `langgraph 0.6.11` 和 `langchain-core 0.3.86` 后，真实消息 round-trip smoke test 通过。
- 全量测试：103 passed。

## 已知限制

本阶段只处理单个 tool call。多调用并发属于 Phase 8，`interrupt/resume` 审批桥接属于 Phase 9。当前仍不支持分布式锁、完整 Graph 工厂或自动推断 Tool 权限。
