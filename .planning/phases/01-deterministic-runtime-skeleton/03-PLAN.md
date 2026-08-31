---
phase: 01-deterministic-runtime-skeleton
plan: 03
type: implementation
wave: 3
depends_on:
  - 02-PLAN
files_modified:
  - src/agentguard/events/model.py
  - src/agentguard/events/sinks.py
  - src/agentguard/cli.py
  - examples/first_vertical_slice.py
  - tests/unit/test_event_sinks.py
  - tests/integration/test_cli_run.py
  - learning/01-agent-loop.md
autonomous: false
requirements:
  - EVENT-01
  - REPORT-01
  - DX-01
  - DX-02
  - DX-03
---

<objective>
Make the deterministic run observable through structured Events, in-memory and JSONL sinks, and one local CLI example.
</objective>

<learning_goal>
Understand the difference between current decision state, complete event history, ordinary diagnostic logs, and future resumable checkpoints.
</learning_goal>

<tasks>

<task type="implementation">
  <name>Add the Phase 1 Event model and sinks</name>
  <files>src/agentguard/events/model.py, src/agentguard/events/sinks.py, tests/unit/test_event_sinks.py</files>
  <action>Emit structured events for run start, action proposed, tool start, tool success/failure, and run finish. Implement only InMemoryEventSink and JsonlEventSink behind a small sink protocol. Use JSON-serializable event payloads and deterministic field names; do not store raw exceptions or claim checkpoint semantics.</action>
  <verify>Test event ordering, JSONL round-trip parsing, and failure event serialization.</verify>
  <acceptance_criteria>The same Runtime can use either sink without changing Router or Tool code, and JSONL contains enough data to explain the tested run.</acceptance_criteria>
</task>

<task type="implementation">
  <name>Expose the first vertical slice through CLI</name>
  <files>src/agentguard/cli.py, examples/first_vertical_slice.py, tests/integration/test_cli_run.py</files>
  <action>Create one small command that runs an echo→finish scripted scenario, prints the terminal status/reason, and writes a JSONL event file. Keep CLI configuration intentionally narrow and avoid service/database configuration.</action>
  <verify>Run the CLI in a temporary output directory; assert exit behavior, terminal summary, and parseable JSONL output.</verify>
  <acceptance_criteria>A new developer can run one local command and inspect the complete structured event sequence without API keys or infrastructure.</acceptance_criteria>
</task>

<task type="checkpoint">
  <name>Phase 1 explanation and evidence review</name>
  <files>learning/01-agent-loop.md</files>
  <action>Complete the learning note using real code/tests: explain State versus Event versus Checkpoint; typed Action rationale; sync/async execution boundary; what broke; and what Phase 1 deliberately does not solve.</action>
  <verify>Review the note alongside one successful and one failing JSONL run. Confirm no planned timeout/retry/loop-detection claim is written as completed.</verify>
  <acceptance_criteria>The Phase 1 evidence can support an honest explanation of the Runtime skeleton and its limitations.</acceptance_criteria>
</task>

</tasks>

<verification>
- Unit and integration tests pass.
- The example CLI run produces a parseable ordered JSONL event stream.
- A failing Tool run records the failure and explicit terminal reason.
- Documentation clearly distinguishes Event logs from future checkpoints.
</verification>

<success_criteria>
- The first deterministic vertical slice runs locally and terminates with explicit evidence.
- Phase 1 requirements are demonstrably covered by tests and a user-runnable example.
- The learning note is grounded in actual implementation and deliberate failures.
</success_criteria>

---
*Plan created: 2026-08-31*
