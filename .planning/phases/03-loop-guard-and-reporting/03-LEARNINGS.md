---
phase: 03
phase_name: "loop-guard-and-reporting"
project: "AgentGuard"
generated: "2026-09-01"
counts:
  decisions: 5
  lessons: 4
  patterns: 4
  surprises: 2
missing_artifacts:
  - "VERIFICATION.md"
---

# Phase 03 Learnings: loop-guard-and-reporting

## Decisions

### Use exact canonical Action signatures for the first loop guard
The guard compares Tool name and canonicalized arguments. Mapping keys are sorted, list order is preserved, and scalar types remain distinct; semantic similarity and Tool result text are excluded.

**Rationale:** Exact signatures are deterministic, explainable, and independent of model APIs. Embedding- or LLM-based similarity would add cost, randomness, and false-positive risk before the basic behavior is understood.
**Source:** 03-PLAN.md; SUMMARY.md

### Trigger after three consecutive identical proposals
The Runtime observes a repeated signature before Tool execution and terminates on the third occurrence with `LOOP_DETECTED`.

**Rationale:** This bounds repeated side effects while allowing two normal executions for a legitimate repeated request.
**Source:** 03-PLAN.md; SUMMARY.md

### Keep loop protection separate from the step budget
`max_steps` remains the global execution bound, while the Loop Guard handles local consecutive repetition and emits its own stop reason and event.

**Rationale:** The two controls answer different questions: total work versus repeated behavior. Keeping them separate makes termination causes auditable.
**Source:** 03-PLAN.md; SUMMARY.md

### Build reports from typed results plus structured events
The reliability report projects the `RunResult`, ordered event timeline, derived counts, and an evidence-consistency flag into a machine-readable JSON-serializable object.

**Rationale:** Runtime conclusions and observable evidence should be inspectable together without inventing unverified model-quality metrics.
**Source:** 03-PLAN.md; SUMMARY.md

### Treat V0.1 acceptance as a user-visible gate before recovery work
Phase 4 checkpoint/recovery remains deferred until the Runtime core passes CLI, loop, timeout-fallback, and report-evidence acceptance scenarios.

**Rationale:** Recovery adds state durability and duplicate-execution risks; validating the smaller reliability core first gives a stable baseline.
**Source:** 03-UAT.md; ROADMAP.md

---

## Lessons

### A passing unit suite is not enough without a user-flow check
The four acceptance scenarios confirmed that the CLI, loop guard, timeout fallback, and report consistency behavior are observable from the user's perspective. All four passed.

**Context:** V0.1 was validated through a conversational UAT after 53 automated tests passed.
**Source:** 03-UAT.md; SUMMARY.md

### Canonicalization must preserve meaningful distinctions
Equivalent dictionary ordering should compare equal, but list ordering and scalar type differences must remain different signatures.

**Context:** Loop-guard tests covered reordered mappings, changed arguments, list order, reset behavior, and threshold semantics.
**Source:** 03-PLAN.md; SUMMARY.md

### Guard placement determines side-effect safety
Checking the signature before Tool execution means the third repeated proposal is recorded and stopped without a third Tool call.

**Context:** The integration scenario used an endlessly repeating Router and observed exactly two Tool invocations.
**Source:** 03-PLAN.md; SUMMARY.md; 03-UAT.md

### Reports need to distinguish conclusion from evidence
A `RunResult` can say `completed` even when the event stream lacks a terminal event; the report must expose that inconsistency instead of silently trusting one source.

**Context:** The report tests intentionally supplied a truncated event stream and expected `evidence_consistent` to be false.
**Source:** 03-PLAN.md; 03-UAT.md

---

## Patterns

### Pre-execution policy observation
Observe and evaluate an Action before dispatching it to the Tool executor. Use this for policies whose purpose is to prevent side effects.

**When to use:** Loop detection, permission checks, budget checks, and other admission-control rules.
**Source:** 03-PLAN.md; SUMMARY.md

### Structured event evidence alongside terminal results
Emit typed events during execution and retain a terminal `RunResult`; derive reports from both rather than replacing one with the other.

**When to use:** Systems that need debugging, auditability, replay analysis, or operational metrics.
**Source:** 03-PLAN.md; SUMMARY.md

### Deterministic scenario-driven integration tests
Use scripted Routers and small deterministic Tools to force a failure mode, then assert both the final result and the event trace.

**When to use:** Runtime reliability features where model nondeterminism would make regressions difficult to reproduce.
**Source:** 03-PLAN.md; 03-UAT.md

### Bilingual learning notes tied to implementation evidence
Capture the same design decision, observed failure, and trade-off in Chinese and English notes, with tests and events as evidence.

**When to use:** Learning-first open-source work intended for collaboration, documentation, and résumé-ready explanation.
**Source:** SUMMARY.md; learning/zh-CN/03-loop-detection.md; learning/en/03-loop-detection.md

---

## Surprises

### A syntactic guard is useful but intentionally incomplete
Exact signatures reliably stop identical consecutive Actions, but they miss semantic loops with slightly changing arguments, non-consecutive repetitions, and unchanged-result cycles.

**Impact:** Semantic similarity, window detection, and result-based heuristics must remain explicit future work rather than being implied by the current guard.
**Source:** SUMMARY.md; learning/zh-CN/03-loop-detection.md

### Evidence consistency is a separate reliability dimension
A run can have a plausible terminal summary while its event evidence is missing or contradictory.

**Impact:** Operational reporting needs a consistency signal in addition to status and stop reason; otherwise incomplete telemetry can look like a clean run.
**Source:** 03-UAT.md; tests/unit/test_report.py

