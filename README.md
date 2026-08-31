# AgentGuard

AgentGuard is a learning-first reliability control and fault-injection toolkit for Agent Runtimes.

V0.1 starts as a small Python library and CLI for deterministic scripted agents. It focuses on bounded tool execution, timeout/cancellation, safe retry semantics, loop detection, structured events, and reproducible failure scenarios.

This project complements [AstraLoom](https://github.com/Gsssst/AstraLoom): AstraLoom explores building an AI research application; AgentGuard explores how to keep long-running Agent Runtimes reliable and explainable under failure.

## Status

Early design / project initialization. See [`.planning/PROJECT.md`](.planning/PROJECT.md), [requirements](.planning/REQUIREMENTS.md), and [roadmap](.planning/ROADMAP.md).

## Learning Contract

For each core module:

1. Understand the problem and compare alternatives.
2. Implement the smallest slice.
3. Deliberately break it and debug the failure.
4. Read mature implementations for comparison.
5. Record evidence, final design, and trade-offs in `learning/`.

No feature or metric is considered complete until it is backed by code, tests, and an explainable run.
