---
phase: 03-loop-guard-and-reporting
plan: 01
type: implementation
wave: 1
depends_on:
  - ../02-tool-failure-boundaries/02-PLAN
files_modified:
  - src/agentguard/domain/actions.py
  - src/agentguard/domain/state.py
  - src/agentguard/domain/runtime.py
  - src/agentguard/runtime/loop_guard.py
  - src/agentguard/runtime/engine.py
  - src/agentguard/events/model.py
  - tests/unit/test_loop_guard.py
  - tests/integration/test_runtime_loop.py
autonomous: false
requirements:
  - GUARD-01
  - GUARD-02
  - LOOP-03
  - EVENT-01
---

<objective>
Detect consecutive repeated canonical Actions and terminate an Agent Run with an explicit `LOOP_DETECTED` reason while preserving explainable events.
</objective>

<learning_goal>
Understand the difference between syntactic repetition and semantic similarity, and why a conservative deterministic guard is appropriate before model-based detection.
</learning_goal>

<tasks>

<task type="implementation">
  <name>Add canonical Action signatures and loop policy</name>
  <files>src/agentguard/runtime/loop_guard.py, src/agentguard/domain/actions.py, tests/unit/test_loop_guard.py</files>
  <action>Canonicalize `CallTool` name and arguments with sorted mapping keys, preserved list order, and type-stable scalar encoding. Track consecutive identical signatures and trigger after three occurrences. A different Action resets the counter. Do not use embeddings or Tool result contents.</action>
  <verify>Test equivalent dictionary ordering, distinct argument values, list ordering, reset behavior, and the three-occurrence threshold.</verify>
  <acceptance_criteria>The loop decision is deterministic, explainable, and independent of model APIs or result text.</acceptance_criteria>
</task>

<task type="implementation">
  <name>Integrate Loop Guard with Runtime</name>
  <files>src/agentguard/domain/state.py, src/agentguard/domain/runtime.py, src/agentguard/runtime/engine.py, src/agentguard/events/model.py, tests/integration/test_runtime_loop.py</files>
  <action>Add `LOOP_DETECTED` to StopReason, run the guard before executing a repeated CallTool, and emit a loop-detected event containing signature, consecutive count, and threshold. Preserve max-step behavior and ensure a different Action resets consecutive repetition.</action>
  <verify>Run an endless repeated-action scenario and assert it terminates on the third proposed signature without executing a fourth Tool call. Test a non-looping sequence with changing arguments.</verify>
  <acceptance_criteria>Repeated actions terminate deterministically and the event stream explains why execution stopped.</acceptance_criteria>
</task>

<task type="checkpoint">
  <name>Break the guard and document trade-offs</name>
  <files>learning/zh-CN/03-loop-detection.md, learning/en/03-loop-detection.md, docs/decisions/004-phase-3-loop-guard.md</files>
  <action>Deliberately test false-positive candidates (pagination/different arguments) and a non-consecutive repetition. Record why the guard uses exact canonical signatures and why semantic detection is deferred.</action>
  <verify>Review actual event traces and test evidence; ensure notes distinguish loop detection from max-step protection.</verify>
  <acceptance_criteria>Both language notes describe verified behavior and known false-positive/false-negative trade-offs.</acceptance_criteria>
</task>

<task type="implementation">
  <name>Build a report from RunResult and Events</name>
  <files>src/agentguard/reporting/report.py, src/agentguard/events/model.py, tests/unit/test_report.py</files>
  <action>Implement a report projection that combines terminal summary, ordered event timeline, and derived counts for tool calls, failures, retries, steps, and loop detection. Detect missing/inconsistent terminal evidence and mark the report accordingly. Keep the report machine-readable and JSON-serializable.</action>
  <verify>Test successful, failed, loop-detected, and truncated/inconsistent event streams.</verify>
  <acceptance_criteria>Reports explain both what the Runtime concluded and what the event evidence supports, without adding unverified LLM metrics.</acceptance_criteria>
</task>

</tasks>

<verification>
- Loop guard unit and integration tests pass.
- Three consecutive identical canonical signatures stop before a fourth Tool execution.
- Different arguments and non-consecutive repetitions do not trigger the Phase 3 guard.
- Reports contain terminal summary, timeline, derived metrics, and inconsistency flags.
- No semantic model, external service, or checkpoint dependency is introduced.
</verification>

<success_criteria>
- Agent loops are bounded by an explainable deterministic guard in addition to max steps.
- A complete run can be summarized and audited from typed results and structured events.
- Chinese and English learning notes capture real failure evidence and trade-offs.
</success_criteria>

---
*Plan created: 2026-09-01*
