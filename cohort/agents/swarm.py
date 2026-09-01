"""Real concurrent multi-agent orchestration (ROADMAP.md "Scope revision",
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
) -> list[list[dict[str, Any]] | BaseException]:
    """Runs every (worker, instructions) pair concurrently. Returns results
    in the same order as `assignments`; a worker that raised gets its
    exception object in that slot instead of a log, rather than aborting
    every other in-flight worker."""
    return await asyncio.gather(
        *(worker.run_async(instructions, max_turns=max_turns) for worker, instructions in assignments),
        return_exceptions=True,
    )
