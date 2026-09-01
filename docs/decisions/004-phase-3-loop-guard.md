# ADR 004: Deterministic Loop Guard

**Status:** Accepted  
**Date:** 2026-09-01

## Decision

Use canonical Tool name + arguments as the loop signature. Detect three consecutive identical signatures and terminate before the third Tool execution. Different Actions reset the counter, and Tool result contents do not affect the Phase 3 decision.

## Rationale

This policy is deterministic, easy to explain, and prevents a repeated side effect before it occurs. Semantic similarity and windowed repetition need additional assumptions and are deferred until a benchmark can measure false positives and false negatives.

## Consequences

The guard may miss semantically equivalent Actions with changed arguments and may not detect non-consecutive cycles. `max_steps` remains the global safety net.

## Evidence

Loop unit tests and Runtime integration tests show stable canonicalization, reset behavior, a three-occurrence threshold, and only two actual Tool executions in a three-proposal loop.
