"""The first deterministic AgentGuard scenario.

Run with:
    PYTHONPATH=src python -m agentguard.cli run --output /tmp/agentguard-run.jsonl
"""

from agentguard.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
