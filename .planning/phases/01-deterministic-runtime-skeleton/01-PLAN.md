---
phase: 01-deterministic-runtime-skeleton
plan: 01
type: implementation
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - src/agentguard/domain/actions.py
  - src/agentguard/domain/results.py
  - src/agentguard/domain/state.py
  - src/agentguard/domain/runtime.py
  - tests/unit/test_domain_models.py
autonomous: false
requirements:
  - LOOP-01
  - LOOP-02
  - LOOP-03
  - DX-01
---

<objective>
Create the smallest typed domain model for a deterministic AgentGuard run and prove that its values can be constructed, validated, and represented without any external service or LLM.
</objective>

<learning_goal>
Understand the boundary between Agent decision data, Runtime state, Tool results, and terminal run outcomes before implementing execution behavior.
</learning_goal>

<tasks>

<task type="implementation">
  <name>Set up the minimal Python package</name>
  <files>pyproject.toml, src/agentguard/</files>
  <action>Create a minimal installable package configuration and package layout. Do not add runtime dependencies unless a demonstrated need appears. Keep the first command path runnable with the standard library and pytest as the development test dependency.</action>
  <verify>Run the package import check and the focused unit test command.</verify>
  <acceptance_criteria>From a clean checkout, the package imports and the test runner discovers the Phase 1 unit tests.</acceptance_criteria>
</task>

<task type="implementation">
  <name>Define typed Actions, ToolResult, RunState, and terminal enums</name>
  <files>src/agentguard/domain/actions.py, src/agentguard/domain/results.py, src/agentguard/domain/state.py, src/agentguard/domain/runtime.py, tests/unit/test_domain_models.py</files>
  <action>Implement immutable or safely-constructed Python objects for CallTool and Finish; ToolResult with SUCCESS/FAILED statuses and serializable error fields; RunStatus and the Phase 1 StopReason values; RunState with run_id, step, status, last_result, and bounded recent history. Define explicit validation for empty tool names, invalid step values, and inconsistent terminal state. Keep timeout/retry/loop-specific values out of this phase.</action>
  <verify>Write and run tests for valid construction, invalid construction, enum stability, and the recent-history bound. Inspect the representations and confirm they do not retain raw exception objects.</verify>
  <acceptance_criteria>The model tests pass and each object has a clear, documented responsibility that matches 01-CONTEXT.md.</acceptance_criteria>
</task>

<task type="checkpoint">
  <name>Review the domain model before execution code</name>
  <files>docs/decisions/001-phase-1-domain-model.md, learning/01-agent-loop.md</files>
  <action>Stop after the model tests pass. Record the problem, alternatives considered, chosen boundaries, and at least one open question for the execution loop. The human developer must be able to explain why Router decisions are typed objects and why RunState is not the complete event history.</action>
  <verify>Manually review the note against the passing tests; do not proceed to the next plan until the model is understood.</verify>
  <acceptance_criteria>A short decision note and learning note exist, grounded in the actual model code and test behavior.</acceptance_criteria>
</task>

</tasks>

<verification>
- `python -c "import agentguard"` succeeds in the project environment.
- Focused Phase 1 unit tests pass.
- Tests demonstrate both valid and invalid typed model construction.
- No external model API, database, Redis, RabbitMQ, or LangGraph dependency is required.
</verification>

<success_criteria>
- The package has a typed domain vocabulary for Action, ToolResult, RunState, RunStatus, and StopReason.
- The state model keeps only bounded recent history while leaving complete audit history to a future EventSink.
- The developer can explain and review the model before any loop execution code is added.
</success_criteria>

---
*Plan created: 2026-08-31*
