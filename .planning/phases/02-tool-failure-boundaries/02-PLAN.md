---
phase: 02-tool-failure-boundaries
plan: 01
type: implementation
wave: 1
depends_on:
  - ../01-deterministic-runtime-skeleton/03-PLAN
files_modified:
  - src/agentguard/domain/results.py
  - src/agentguard/runtime/tool.py
  - src/agentguard/runtime/policy.py
  - src/agentguard/events/model.py
  - tests/unit/test_retry_policy.py
  - tests/unit/test_tool_timeout.py
autonomous: false
requirements:
  - TOOL-01
  - TOOL-02
  - TOOL-03
  - FAULT-01
---

<objective>
Add the first bounded Tool failure boundary: layered timeout configuration, cooperative async cancellation, explicit sync-thread limitation, failure classification, retry-safety metadata, and deterministic exponential backoff.
</objective>

<learning_goal>
Understand what a timeout can and cannot guarantee, why retry safety is separate from transient failure, and how attempt budgets prevent retry storms.
</learning_goal>

<tasks>

<task type="implementation">
  <name>Extend Tool metadata and failure results</name>
  <files>src/agentguard/domain/results.py, src/agentguard/runtime/tool.py</files>
  <action>Add `TIMED_OUT` and `CANCELLED` result statuses, serializable `FailureKind` values, and Tool metadata for timeout and `RetrySafety`. Keep default retry safety `UNKNOWN`, default timeout inherited from Runtime, and preserve the sync/async unified executor boundary.</action>
  <verify>Unit-test metadata defaults, explicit Tool timeout overriding Runtime default, and serializable timeout/cancellation result construction.</verify>
  <acceptance_criteria>Tool metadata expresses the agreed policy without allowing a Router Action to bypass Runtime limits.</acceptance_criteria>
</task>

<task type="implementation">
  <name>Implement timeout and cancellation behavior</name>
  <files>src/agentguard/runtime/tool.py, tests/unit/test_tool_timeout.py</files>
  <action>Wrap async Tool execution with a deadline and cooperative cancellation. Adapt sync Tools through the existing worker-thread path; after timeout stop awaiting and return `TIMED_OUT`, while documenting/testing that the underlying thread may continue. Ensure timeout source and effective duration are available to the caller for event recording.</action>
  <verify>Use short deterministic delays to prove async timeout returns within the deadline and receives cancellation; use a sync side-effect probe to demonstrate the weaker thread guarantee without relying on flaky wall-clock assertions.</verify>
  <acceptance_criteria>Runtime regains control after timeout, async cancellation is attempted, sync limitations are visible, and no timeout path hangs the test suite.</acceptance_criteria>
</task>

<task type="implementation">
  <name>Implement bounded retry policy</name>
  <files>src/agentguard/runtime/policy.py, src/agentguard/runtime/tool.py, tests/unit/test_retry_policy.py</files>
  <action>Implement `RetryPolicy` with `max_attempts` (including the initial attempt), transient-failure eligibility, `SAFE` retry-safety requirement, deterministic exponential backoff, and no jitter. Default to one attempt. Do not automatically retry sync Tool timeouts, permanent failures, cancelled results, unknown/unsafe Tools, or idempotency-key-required Tools without an actual key mechanism.</action>
  <verify>Test attempt counts, eligible/ineligible combinations, backoff schedule, exhaustion, and the distinction between Runtime attempts and later Router fallback Actions.</verify>
  <acceptance_criteria>Every automatic retry is bounded, policy-justified, and distinguishable from a new Router-requested Tool call.</acceptance_criteria>
</task>

<task type="checkpoint">
  <name>Break the failure boundary and record evidence</name>
  <files>learning/zh-CN/02-tool-timeout.md, learning/en/02-tool-timeout.md, docs/decisions/003-phase-2-timeout-retry.md</files>
  <action>Run deliberate async timeout, sync timeout with a side-effect probe, transient SAFE retry, and unsafe/permanent no-retry scenarios. Record actual observations, uncertainty, and why deterministic backoff was chosen before any jitter experiment.</action>
  <verify>Review tests and captured events/results; ensure the notes never claim that a sync timeout kills the underlying thread or that metadata proves real-world idempotency.</verify>
  <acceptance_criteria>Chinese and English notes contain the same verified facts and clearly separate Runtime timeout, cancellation attempt, retry policy, and Router fallback.</acceptance_criteria>
</task>

</tasks>

<verification>
- Focused timeout and retry tests pass deterministically.
- Async timeout returns control within the configured deadline.
- Sync timeout limitation is demonstrated and documented.
- Only `SAFE + TRANSIENT` failures are automatically retried in the initial implementation.
- `max_attempts` includes the first attempt, and exponential delays are deterministic with jitter disabled.
</verification>

<success_criteria>
- Tool failure behavior is bounded, explicit, and explainable.
- Retry safety and failure kind are separate policy dimensions.
- The first Phase 2 failure scenarios can be reproduced without external services.
</success_criteria>

---
*Plan created: 2026-09-01*
