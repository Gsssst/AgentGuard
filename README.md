# AgentGuard

[![CI](https://github.com/Gsssst/AgentGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/Gsssst/AgentGuard/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

AgentGuard is a small, learning-first reliability and fault-injection toolkit
for Python Agent runtimes. It puts explicit boundaries around tool execution so
an Agent can terminate predictably, fail safely, and leave enough structured
evidence to explain what happened.

Version **0.3.0** adds an optional LangGraph adapter with guarded multi-tool
execution and digest-bound human approval.

## Why AgentGuard?

Tool-calling Agents often fail outside the model itself: a tool hangs, retries a
non-idempotent action, competes for a shared resource, repeats the same action,
or resumes after approval with stale inputs. AgentGuard makes those boundaries
explicit and testable.

It complements [AstraLoom](https://github.com/Gsssst/AstraLoom): AstraLoom is an
AI research application, while AgentGuard focuses on the runtime mechanics that
keep Agent execution bounded and explainable.

## What v0.3 Includes

- Deterministic Agent loop with explicit termination reasons.
- Tool timeouts, cancellation, retry policies, and typed failure kinds.
- Loop detection plus step/time budgets and reliability reports.
- Local checkpoint/resume and crash-recovery evidence.
- Capability permissions, redaction, action digests, and approval boundaries.
- Process-local resource locks and bounded concurrent tool batches.
- Optional `GuardedToolNode` and `ToolGuard` for LangGraph/LangChain tools.
- Per-call LangGraph `interrupt()` / `Command(resume=...)` approval.
- Ordered structured `ToolMessage` results with original `tool_call_id` values.
- Deterministic tests, deliberate fault scenarios, and paired learning notes.

## Installation

AgentGuard is not published to PyPI yet. Install it from a local clone:

```bash
git clone https://github.com/Gsssst/AgentGuard.git
cd AgentGuard
python -m pip install -e .
```

Install the verified LangGraph integration:

```bash
python -m pip install -e '.[langgraph]'
```

The core package does not import LangGraph. Adapter dependencies are loaded only
when `agentguard.integrations.langgraph` is used.

## Quick Start

Run the deterministic CLI example and write its event evidence to JSONL:

```bash
agentguard run --output run.jsonl
```

Expected output:

```text
status: completed
stop_reason: completed
events: run.jsonl
```

The output file contains one structured runtime event per line.

## Python Example

```python
import asyncio

from agentguard import CallTool, Finish, JsonlEventSink, RunState, Runtime
from agentguard.runtime.router import ScriptedRouter
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


async def main() -> None:
    async def echo(text: str) -> str:
        return text

    runtime = Runtime(
        executor=ToolExecutor(ToolRegistry({"echo": echo})),
        event_sink=JsonlEventSink("run.jsonl"),
    )
    result = await runtime.run(
        ScriptedRouter([
            CallTool("echo", {"text": "hello from AgentGuard"}),
            Finish("done"),
        ]),
        RunState("example-run"),
    )
    print(result.status, result.stop_reason)


asyncio.run(main())
```

## LangGraph Adapter

```python
from langchain_core.tools import tool

from agentguard import Runtime
from agentguard.integrations.langgraph import GuardedToolNode, ToolGuard
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


@tool
def read_note(note_id: str) -> str:
    """Read one note."""
    return f"note:{note_id}"


node = GuardedToolNode(
    [read_note],
    runtime=Runtime(ToolExecutor(ToolRegistry())),
    guards={
        "read_note": ToolGuard(
            capabilities={"read"},
            timeout=2.0,
        )
    },
)
```

Use `node.prepare` and `node.approval` as separate LangGraph nodes when approval
can interrupt execution. This keeps direct side effects from replaying and
prevents pending placeholders from being appended beside final results in a
standard `MessagesState` graph.

## Verification

Install development and adapter dependencies, then run the suite:

```bash
python -m pip install -e '.[dev,langgraph]'
pytest -q
```

The v0.3 milestone closes with **136 passing tests**, including real LangGraph
`StateGraph`, `MemorySaver`, and `MessagesState` integration tests.

## Project Layout

```text
src/agentguard/       Runtime, events, checkpointing, policies, integrations
tests/unit/           Deterministic component tests
tests/integration/    Runtime and optional LangGraph integration tests
examples/             Minimal runnable examples
learning/zh-CN/       Chinese learning and interview-review notes
learning/en/          English open-source learning notes
docs/decisions/       Architecture decision records
```

## Current Boundaries

AgentGuard v0.3 is an alpha-stage local library, not a production control plane.

- Resource locks and event sinks are process-local.
- External side effects are at-least-once-aware, not exactly-once.
- LangGraph compatibility is verified with `langgraph==0.6.11` and
  `langchain-core==0.3.86` on Python 3.12.9.
- There is no hosted service, multi-tenancy, distributed lock, or remote
  authorization system.
- Human-facing approval payloads are redacted, while original arguments remain
  in trusted checkpoint state for digest recomputation.

## Contributing

Contributions and issue reports are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md).
For sensitive vulnerabilities, follow [SECURITY.md](SECURITY.md) instead of
opening a public issue.

## Learning Contract

Every core capability follows the same loop:

1. Understand the failure mode and compare alternatives.
2. Implement the smallest inspectable slice.
3. Deliberately break it and debug the result.
4. Verify it with deterministic tests.
5. Record the final design, evidence, and limitations in `learning/`.

## License

Licensed under the [Apache License 2.0](LICENSE).
