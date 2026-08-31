---
phase: 01-deterministic-runtime-skeleton
plan: 02
type: implementation
wave: 2
depends_on:
  - 01-PLAN
files_modified:
  - src/agentguard/runtime/router.py
  - src/agentguard/runtime/tool.py
  - src/agentguard/runtime/engine.py
  - tests/unit/test_tool_execution.py
  - tests/integration/test_runtime_loop.py
autonomous: false
requirements:
  - LOOP-01
  - LOOP-02
  - LOOP-03
  - TOOL-02
  - DX-02
---

<objective>
Implement one deterministic `State + Router` execution loop that runs one typed Action per turn and ends with an explicit status and reason.
</objective>

<learning_goal>
Trace the complete control flow from Router decision through Runtime validation, Tool execution, state update, and termination.
</learning_goal>

<tasks>

<task type="implementation">
  <name>Define Router and Tool boundaries</name>
  <files>src/agentguard/runtime/router.py, src/agentguard/runtime/tool.py, tests/unit/test_tool_execution.py</files>
  <action>Define the minimal Router protocol over RunState and a small Tool registry/executor boundary. Support async callables directly and adapt sync callables behind the same async execute method. Execute only one tool per turn. Do not implement timeout, retry, batch execution, or parallel scheduling.</action>
  <verify>Run tests proving one sync tool and one async tool both produce the expected ToolResult through the same async executor entry point.</verify>
  <acceptance_criteria>Router and Tool responsibilities remain separate, and both callable types work sequentially without adding concurrency policy.</acceptance_criteria>
</task>

<task type="implementation">
  <name>Implement the minimal Runtime loop</name>
  <files>src/agentguard/runtime/engine.py, tests/integration/test_runtime_loop.py</files>
  <action>Repeatedly ask the Router for one Action, validate it, execute CallTool through the registry, update RunState, or terminate on Finish. Enforce the configured step budget. Convert unknown tools, malformed/unknown actions, and Tool exceptions into explicit Phase 1 outcomes. Keep the loop independent from LangGraph while following the agreed state-and-router model.</action>
  <verify>Run integration tests for successful echo→finish, unknown tool, Tool exception, invalid action, and step-budget exhaustion.</verify>
  <acceptance_criteria>Every tested run terminates deterministically with the expected RunStatus and StopReason; no path can run indefinitely under the Phase 1 step budget.</acceptance_criteria>
</task>

<task type="checkpoint">
  <name>Break and trace the loop</name>
  <files>learning/01-agent-loop.md</files>
  <action>Run at least two deliberate failure cases: a Router returning an unsupported object and a Router that never returns Finish. Trace each transition by hand and record which boundary converts it into INVALID_ACTION or STEP_BUDGET_EXCEEDED.</action>
  <verify>The developer can explain the two failure traces without relying only on final assertions.</verify>
  <acceptance_criteria>The learning note records actual failing behavior, the Runtime response, and remaining uncertainties.</acceptance_criteria>
</task>

</tasks>

<verification>
- Focused Tool executor tests pass for sync and async callables.
- Integration tests cover all Phase 1 stop reasons.
- A non-finishing Router is bounded by max steps.
- No parallel tool execution or framework dependency is present.
</verification>

<success_criteria>
- A scripted Router can execute a deterministic Tool call and explicitly finish.
- Tool and Router failures become typed outcomes instead of uncaught process failures.
- The developer can trace the full loop and the two deliberate failure cases.
</success_criteria>

---
*Plan created: 2026-08-31*
