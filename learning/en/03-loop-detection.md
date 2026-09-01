# Agent Loop Detection

## Problem

An Agent may repeatedly propose the exact same Tool Action, wasting time and budget or producing duplicate side effects.

## First design

- Build an Action Signature from Tool name and canonicalized arguments.
- Sort mapping keys, preserve list order, and keep scalar types distinct.
- Detect consecutive repetition only; the third identical signature triggers `LOOP_DETECTED`.
- A different Action resets the counter; Tool result content is not part of the decision.
- Check before Tool execution, so the third repeated proposal emits evidence but is not executed.

## What broke / tested

A Router that always returned `CallTool("echo", {"value": 1})` was run. The first two Tool calls executed; the third proposal triggered `LOOP_DETECTED`, leaving the actual Tool call count at 2 and preventing the third side effect.

Different mapping key order produces the same signature; different list order and `1` versus `"1"` produce different signatures. Inserting `Finish` or changing arguments resets consecutive counting.

## Trade-offs

Exact signatures are deterministic and explainable, but they cannot detect the same intent expressed with slightly different arguments and may miss semantic loops. Embedding/LLM similarity would add cost, nondeterminism, and false-positive risk, so it is deferred.

Loop Guard differs from `max_steps`: `max_steps` limits total turns, while Loop Guard targets local repeated actions and blocks the repeated Tool before its side effect.

## Verified

Fifty tests pass, covering canonicalization, threshold, counter reset, non-consecutive repetition, and pre-execution Runtime termination.

## Not solved

Semantic loops, non-consecutive window repetition, unchanged-result detection, and model behavior analysis are not implemented.
