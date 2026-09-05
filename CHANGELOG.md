# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-09-04

### Added

- A deterministic Agent runtime loop with explicit termination reasons.
- Tool timeout, cancellation, retry, typed failure, and fault-injection
  boundaries.
- Step and time budgets, loop detection, structured events, and reliability
  reports.
- Local checkpoint/resume and crash-recovery behavior.
- Capability policies, approval decisions, argument redaction, and
  digest-bound approval validation.
- Process-local resource locks and ordered concurrent tool-batch execution.
- An optional LangGraph adapter with guarded single- and multi-tool execution.
- Per-call LangGraph `interrupt()` and `Command(resume=...)` approval support.
- Chinese and English learning notes backed by deterministic tests.

### Fixed

- Replaced pending approval results in LangGraph `MessagesState` instead of
  appending duplicate `ToolMessage` entries after resume.

### Security

- Guards fail closed when tool policies are missing.
- Agent-visible failure messages avoid leaking raw exceptions and sensitive
  arguments.
- Resumed approvals are bound to the original action digest to reject stale or
  modified tool calls.

[Unreleased]: https://github.com/Gsssst/AgentGuard/compare/v0.3...HEAD
[0.3.0]: https://github.com/Gsssst/AgentGuard/releases/tag/v0.3
