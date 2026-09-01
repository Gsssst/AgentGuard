# AgentGuard — Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-31)

**Core value:** An Agent Runtime must terminate, remain bounded, and leave enough evidence to explain what happened when tools fail or the agent repeats itself.
**Current focus:** Phase 4 Wave 2 complete; evaluation scenarios are next

## Current Position

- Project initialized.
- V0.1 scope agreed: Runtime developers, scripted-first, Python library + CLI.
- Phase 1 Runtime skeleton committed.
- Phase 2 Tool failure boundaries committed.
- Phase 3 loop guard and reliability reporting implemented locally.
- 53 automated tests pass.
- V0.1 acceptance and Phase 3 learning extraction completed.
- Phase 4 checkpoint/recovery and reliability evaluation decisions captured.
- Phase 4 research, pattern mapping, and three-wave implementation plans drafted.
- Phase 4 Plan 04-01 checkpoint foundation implemented; 61 tests pass.
- Phase 4 Plan 04-02 Runtime recovery integration implemented; 64 tests pass.

## Session Continuity

- Keep implementation small and inspectable.
- For every core feature, capture a failure and a learning note.
- Do not add Java, RabbitMQ, or Redis without a demonstrated requirement.
