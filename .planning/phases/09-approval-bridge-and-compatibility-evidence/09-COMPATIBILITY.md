---
phase: 09
phase_name: "approval-bridge-and-compatibility-evidence"
project: "AgentGuard"
generated: "2026-09-04"
scope: "bounded LangGraph interrupt/resume evidence"
verified_versions:
  python: "3.12.9"
  langgraph: "0.6.11"
  langchain-core: "0.3.86"
  pytest: "8.3.5"
---

# Phase 09 Compatibility Evidence

This note records reproducible observations for the AgentGuard approval bridge. It is a bounded compatibility claim for the public API combination tested below, not a promise for every historical LangGraph release and not a production HA/exactly-once statement.

## 1. Verified environment

| Component | Observed version | How observed |
|---|---:|---|
| Python | 3.12.9 | `python -c 'import sys; print(sys.version)'` |
| langgraph | 0.6.11 | `importlib.metadata.version("langgraph")` |
| langchain-core | 0.3.86 | `importlib.metadata.version("langchain-core")` |
| pytest | 8.3.5 | `importlib.metadata.version("pytest")` |

The repository optional extra is bounded to these LangGraph packages in `pyproject.toml`:

```toml
langgraph = [
    "langgraph==0.6.11",
    "langchain-core==0.3.86",
]
```

## 2. Reproduction commands

From a fresh checkout with network access, the intended clean-install command is:

```bash
python3 -m venv .venv-phase9
. .venv-phase9/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[langgraph]'
PYTHONPATH=src pytest -q
```

In the 2026-09-04 sandbox, the first isolated install could not download the build-isolation requirement `setuptools>=68` because registry access was unavailable. No package name was substituted. The locally reproducible fallback used an existing system package set and disabled build isolation:

```bash
python3 -m venv --system-site-packages /tmp/agentguard-phase9-venv
. /tmp/agentguard-phase9-venv/bin/activate
python -m pip install --no-build-isolation -e '.[langgraph]'
python -c 'import sys, importlib.metadata as m; print(sys.version); print(m.version("langgraph")); print(m.version("langchain-core"))'
```

The fallback printed Python 3.12.9, `langgraph 0.6.11`, and `langchain-core 0.3.86`.

## 3. Test commands and observed results

### Targeted approval and real integration tests

```bash
PYTHONPATH=src pytest -q \
  tests/unit/test_langgraph_approval.py \
  tests/integration/test_langgraph_approval.py \
  tests/integration/test_langgraph_optional.py
```

Observed result: **14 passed in 0.18s**.

### Full source-tree suite

```bash
PYTHONPATH=src pytest -q
```

Observed result: **132 passed in 0.89s**.

The exact wall-clock values are informational; the pass counts and test paths are the compatibility evidence.

### Optional-dependency skip behavior

When LangGraph imports are intentionally blocked, adapter-specific modules use `pytest.importorskip` and report an actionable reason, for example:

```text
Skipped: install agentguard[langgraph] for LangGraph approval integration tests
```

The Plan 09-02 blocked-import run observed **91 passed, 12 skipped**. Core AgentGuard tests remained runnable. When the optional packages are installed, the same integration modules execute instead of silently skipping (D-16).

## 4. Real StateGraph interrupt/resume evidence

`tests/integration/test_langgraph_approval.py` composes a public `StateGraph` with:

- a `prepare` node that executes direct calls and returns a JSON-serializable preparation projection;
- an `approval` node that calls `langgraph.types.interrupt(payload)` once for all pending calls;
- `langgraph.checkpoint.memory.MemorySaver` as the graph checkpointer;
- the same `configurable.thread_id` for the initial invocation and the resume invocation;
- `langgraph.types.Command(resume=decision_map)` to continue the paused graph.

Observed scenarios:

1. A mixed batch executes the safe `read` call before suspension; the `write` call has zero invocations while paused.
2. Resuming with the matching digest and `approved: true` executes `write` exactly once in the two-node graph. The direct `read` call remains at one invocation, proving it was not replayed by approval resume in this composition.
3. Partial approval returns an ordered result for every original call; an omitted decision becomes `PermissionDenied` and its tool is not called.
4. A tampered digest rejects only its call, and removing a tool before resume yields `UnknownTool` without an unhandled graph exception.
5. Nested sensitive arguments appear as redaction markers in the interrupt JSON, while the underlying digest remains bound to canonical original arguments.

The evidence uses only public `StateGraph`, `START`/`END`, `MemorySaver`, `interrupt`, `Command`, and `configurable.thread_id` APIs. It does not claim that arbitrary single-node graphs have exactly-once side effects.

## 5. Requirement and decision evidence map

| Requirement | Evidence artifact | What is demonstrated |
|---|---|---|
| APPROVAL-01 | `tests/integration/test_langgraph_approval.py` | Pause occurs through `interrupt` before pending tool invocation |
| APPROVAL-02 | `tests/unit/test_langgraph_approval.py`, integration redaction test | Redacted arguments, original call ID, per-call digest |
| APPROVAL-03 | Real StateGraph tests with `MemorySaver` and `Command(resume=...)` | LangGraph owns pause/checkpoint/recovery state |
| APPROVAL-04 | Unit partial/missing decision tests | Independent decisions keyed by `tool_call_id` |
| APPROVAL-05 | Digest mismatch and argument tamper tests | Per-call recomputation and fail-closed mismatch |
| APPROVAL-06 | Ordered ToolMessage assertions | Only approved calls execute; denied calls are structured messages |
| COMPAT-03 | `test_langgraph_optional.py` and blocked-import run | Installed path runs; missing extra skips clearly |
| COMPAT-04 | 14 targeted / 132 full test results | Approval, denial, timeout, retry, lock, redaction and digest coverage |
| COMPAT-05 | `09-LEARNINGS.md`, `09-LEARNINGS.en.md` | Paired failure-oriented learning records |

Decision IDs D-01–D-16 are discussed in the paired learning records; D-13 and D-16 are additionally evidenced by the version and skip sections above.

## 6. Bounded compatibility claim and non-claims

**Supported by this evidence:** AgentGuard's Phase 9 adapter is verified with Python 3.12.9, `langgraph==0.6.11`, and `langchain-core==0.3.86`, using the public interrupt/resume and checkpointer APIs listed above. The deterministic fake-tool suite can exercise the adapter boundary without a real LLM provider.

**Not supported or promised by this evidence:**

- every historical or future LangGraph/LangChain version;
- exactly-once external side effects or transactional resume;
- process or cluster high availability;
- cross-process/distributed locks or checkpoints;
- authenticated reviewer identity, RBAC/ABAC, or a remote approval service;
- a frontend approval console or multi-round pending workflow.

These limits are intentional release boundaries, not untested capabilities.

---
*Phase: 09-approval-bridge-and-compatibility-evidence*
*Evidence date: 2026-09-04*
