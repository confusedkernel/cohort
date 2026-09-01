"""Real concurrent multi-agent orchestration (docs/roadmap.md "Scope revision",
agent-society axis step 4 — the deferred piece, now built).

`run_swarm()` is a thin wrapper over `asyncio.gather`; the actual safety
argument for running several `AttestationWorker`s against one shared
`Graph` lives in `attestation_worker.py`'s module docstring and
`run_async()`, not here. This module's only job is fan-out plus one
deliberate choice: `return_exceptions=True`, so one worker's `OpenRouterError`
(a real, documented possibility — transport failures propagate uncaught out
of `run_async()`, unlike tool errors, which are caught and reported back to
the model) doesn't cancel every other concurrently-running worker.

Reputation scoring (step 5) is not part of this — concurrency doesn't change
the reasoning that kept it deferred: that was always about what a *score*
would reward, not about *when* agents run.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .attestation_worker import AttestationWorker


async def run_swarm(
    assignments: list[tuple[AttestationWorker, str]], *, max_turns: int = 6,
    on_tool_call=None, should_stop=None,
) -> list[list[dict[str, Any]] | BaseException]:
    """Runs every (worker, instructions) pair concurrently. Returns results
    in the same order as `assignments`; a worker that raised gets its
    exception object in that slot instead of a log, rather than aborting
    every other in-flight worker.

    `on_tool_call(worker, entry)` fires as each worker makes a tool call, and
    `should_stop()` is consulted between turns by every worker. Both are
    optional, so a script's behaviour is unchanged. They exist for a caller
    watching a swarm in progress (the web UI): without the worker identity in
    the callback, a live view could show *that* six tool calls happened but not
    *which agent* made them — and with distinct declared scopes per agent, that
    attribution is the whole point of running several.

    Deliberately still no channel between workers. Passing progress *outward*
    to one observer is not agent-to-agent messaging (docs/design.md §5 principle 3):
    no worker can see another's callback, results, or transcript."""
    def _hook(worker: AttestationWorker):
        if on_tool_call is None:
            return None
        return lambda entry: on_tool_call(worker, entry)

    return await asyncio.gather(
        *(
            worker.run_async(
                instructions, max_turns=max_turns,
                on_tool_call=_hook(worker), should_stop=should_stop,
            )
            for worker, instructions in assignments
        ),
        return_exceptions=True,
    )
