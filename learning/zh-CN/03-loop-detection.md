# Agent Loop Detection：循环检测

## Problem：问题

Agent 可能反复提出完全相同的 Tool Action，浪费时间和预算，甚至重复产生副作用。

## My first design：第一版设计

- 用 Tool 名称和规范化参数生成 Action Signature。
- 字典 key 排序，列表顺序保留，标量类型保持区分。
- 只检测连续重复；第三次连续相同触发 `LOOP_DETECTED`。
- 不同 Action 重置计数；Tool 结果内容不参与判断。
- 在 Tool 执行前检查，因此第三次重复只记录事件，不执行 Tool。

## What broke / tested：故障与测试

一个永远返回 `CallTool("echo", {"value": 1})` 的 Router 被运行。前两次 Tool 正常执行，第三次提出时触发 `LOOP_DETECTED`，实际 Tool 调用次数为 2，避免了第三次副作用。

字典参数顺序不同会得到相同签名；列表顺序不同、`1` 与 `"1"` 会得到不同签名。插入 `Finish` 或使用不同参数会重置连续计数。

## Trade-offs：权衡

精确签名是可解释且确定性的，但它不能发现参数略有变化的同一意图，也可能漏掉语义循环。语义相似度检测需要 embedding/LLM，会增加成本、随机性和误报风险，因此推迟。

Loop Guard 与 `max_steps` 不同：`max_steps` 限制总执行轮数；Loop Guard 针对局部重复行动，并在副作用前阻止重复调用。

## Verified：已验证

当前 50 个测试通过，包含 canonicalization、阈值、计数重置、非连续重复和 Runtime 执行前终止。

## Not solved：尚未解决

语义循环、窗口内非连续重复、结果无变化检测和模型行为分析尚未实现。
