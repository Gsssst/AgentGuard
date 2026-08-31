"""Small local CLI for the first deterministic vertical slice."""

import argparse
import asyncio
from pathlib import Path

from agentguard.domain.actions import CallTool, Finish
from agentguard.domain.state import RunState
from agentguard.events.sinks import JsonlEventSink
from agentguard.runtime.engine import Runtime
from agentguard.runtime.router import ScriptedRouter
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


async def _run_echo(output: Path) -> int:
    async def echo(text: str) -> str:
        return text

    result = await Runtime(
        executor=ToolExecutor(ToolRegistry({"echo": echo})),
        event_sink=JsonlEventSink(output),
    ).run(
        ScriptedRouter(
            [
                CallTool("echo", {"text": "hello from AgentGuard"}),
                Finish("script_completed"),
            ]
        ),
        RunState("cli-run"),
    )
    print(f"status: {result.status.value}")
    print(f"stop_reason: {result.stop_reason.value}")
    print(f"events: {output}")
    return 0 if result.status.value == "completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="agentguard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run the first local example")
    run_parser.add_argument(
        "--output",
        type=Path,
        default=Path("run.jsonl"),
        help="JSONL event output path (default: run.jsonl)",
    )
    args = parser.parse_args()
    if args.command == "run":
        return asyncio.run(_run_echo(args.output))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
