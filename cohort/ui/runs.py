"""Running an agent from the web UI, with the same guarantees the scripts have.

The goal is parity: everything you can do with `scripts/run_*.py` should be
doable from a browser, and nothing the scripts refuse should become possible
because the caller is a web request instead of a shell.

Four things make that true, and each is a constraint rather than a feature:

**1. One run at a time, enforced by the same lock as everything else.** An
agent run holds the graph's exclusive `flock` for its whole duration —
minutes, not milliseconds — because it writes continuously. So while a run is
active, `POST /api/accept` answers 409, exactly as it would while
`scripts/run_cbeta_demo.py` was running in a terminal. That is not a
limitation introduced here; it is DESIGN.md §5 principle 7 behaving normally,
and the UI's job is to *say so* rather than to work around it.

**2. Spend is capped in code, per run, with a ceiling the client cannot
raise.** `cohort/agents/budget.py` refuses the request that would cross the
cap. The browser chooses a budget, but `max_budget_usd` — set by whoever
started the server — bounds what it may choose. A client-supplied number that
nothing checks is not a budget, it is a suggestion.

**3. The run happens in a background thread, not in the request.** A model
loop takes minutes; an HTTP request that blocked for that long would time out
somewhere unhelpful. `POST /api/run` returns immediately with a run id and
`GET /api/run` reports progress. The thread owns its own `Graph` and its own
event loop, which also satisfies sqlite3's same-thread rule for free — the
same reason `AttestationWorker`'s docstring gives for its own threading model.

**4. The API key never reaches the browser.** It is read server-side from the
environment, the same way the scripts read it. The UI can start a run; it
cannot see the credential that pays for one.

**What is deliberately absent.** There is no queue and no retry. If a run is
already going, starting another is refused with a clear reason rather than
enqueued — a queue would let a researcher accumulate spend they cannot see,
and a retry would make the single-writer rule feel like flakiness.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from ..agents.attestation_worker import AttestationWorker
from ..agents.budget import BudgetedTransport, BudgetExceeded
from ..agents.openrouter import OpenRouterError, load_openrouter_config
from ..eventlog import read_refusals
from ..graph import Graph
from ..schemas import AgentKind, AgentProfile
from ..sources.base import Source

#: What a run may cost unless the operator raises it. Low on purpose: the
#: whole live conjecture run cost $0.004, so a dollar is already generous, and
#: a default that cannot surprise anyone is worth more than a convenient one.
DEFAULT_MAX_BUDGET_USD = 1.00

#: Turn ceiling, same reasoning. A worker that has not finished in this many
#: turns is usually looping, not thinking.
DEFAULT_MAX_TURNS = 8


class RunRejected(RuntimeError):
    """A run could not be started. Carries a reason meant to be shown."""


class Run:
    """One agent run's observable state. Written by the worker thread, read by
    request threads, so every mutation happens under `_lock`."""

    def __init__(self, run_id: str, instructions: str, agent_id: str, budget_usd: float,
                 max_turns: int, model: str) -> None:
        self.id = run_id
        self.instructions = instructions
        self.agent_id = agent_id
        self.budget_usd = budget_usd
        self.max_turns = max_turns
        self.model = model
        self.state = "starting"   # starting | running | finished | failed | stopped
        self.started_at = time.time()
        self.ended_at: float | None = None
        self.tool_calls: list[dict[str, Any]] = []
        self.spend: dict[str, Any] = {
            "budget_usd": budget_usd, "spent_usd": 0.0,
            "remaining_usd": budget_usd, "calls": 0, "unpriced_calls": 0,
        }
        self.error: str | None = None
        self.stopped_early: str | None = None
        self.refusals: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._cancel = threading.Event()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "id": self.id,
                "state": self.state,
                "agent_id": self.agent_id,
                "model": self.model,
                "instructions": self.instructions,
                "max_turns": self.max_turns,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "elapsed_s": round((self.ended_at or time.time()) - self.started_at, 1),
                "tool_calls": list(self.tool_calls),
                "spend": dict(self.spend),
                "error": self.error,
                "stopped_early": self.stopped_early,
                "refusals": list(self.refusals),
                "cancel_requested": self._cancel.is_set(),
            }

    def request_stop(self) -> None:
        """Ask the run to stop after the turn in progress.

        Deliberately cooperative rather than a kill: the in-flight HTTP call
        has already been paid for, and abandoning the thread mid-write could
        leave the projection and the log disagreeing — the one invariant this
        system is built on. So the flag is checked between turns.
        """
        self._cancel.set()


class RunManager:
    """Holds at most one active run for one graph."""

    def __init__(
        self, db_path: Path, log_path: Path, source: Source | None,
        *, max_budget_usd: float = DEFAULT_MAX_BUDGET_USD,
        max_turns: int = DEFAULT_MAX_TURNS,
        transport_factory=None,
    ) -> None:
        self.db_path = db_path
        self.log_path = log_path
        self.source = source
        self.max_budget_usd = max_budget_usd
        self.max_turns = max_turns
        #: test seam, mirroring `complete()`'s own `transport` parameter
        self._transport_factory = transport_factory or (
            lambda budget, on_call: BudgetedTransport(budget, on_call=on_call)
        )
        self._current: Run | None = None
        self._history: list[Run] = []
        self._lock = threading.Lock()

    # --- introspection --------------------------------------------------

    def config(self) -> dict[str, Any]:
        try:
            _, model = load_openrouter_config()
            configured, detail = True, model
        except OpenRouterError as e:
            configured, detail = False, str(e)
        return {
            "runs_enabled": True,
            "corpus_available": self.source is not None,
            "model_configured": configured,
            "model": detail if configured else None,
            "config_error": None if configured else detail,
            "max_budget_usd": self.max_budget_usd,
            "default_budget_usd": min(0.25, self.max_budget_usd),
            "max_turns": self.max_turns,
        }

    def current(self) -> dict[str, Any] | None:
        with self._lock:
            run = self._current
        return run.snapshot() if run else None

    def history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            runs = list(self._history[-limit:])
        return [r.snapshot() for r in reversed(runs)]

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            for run in [self._current, *self._history]:
                if run is not None and run.id == run_id:
                    return run.snapshot()
        return None

    def stop(self) -> dict[str, Any]:
        with self._lock:
            run = self._current
        if run is None:
            raise RunRejected("no run is in progress")
        run.request_stop()
        return run.snapshot()

    # --- starting -------------------------------------------------------

    def start(
        self, instructions: str, *, agent_id: str, budget_usd: float,
        max_turns: int | None = None, corpus_scope: str = "", method_label: str = "",
    ) -> dict[str, Any]:
        if self.source is None:
            raise RunRejected(
                "no corpus is configured on this server, so an agent would have "
                "nothing to search. Start it with --archive/--fts, or set "
                "CBETA_ARCHIVE_PATH and CBETA_FTS_PATH."
            )
        if not instructions.strip():
            raise RunRejected("instructions are required: an agent needs a task")
        if budget_usd <= 0:
            raise RunRejected("budget must be positive")
        if budget_usd > self.max_budget_usd:
            raise RunRejected(
                f"budget ${budget_usd:.2f} exceeds this server's ceiling of "
                f"${self.max_budget_usd:.2f}. The ceiling is set when the server "
                "starts, not by the browser."
            )
        turns = min(max_turns or self.max_turns, self.max_turns)

        try:
            _, model = load_openrouter_config()
        except OpenRouterError as e:
            raise RunRejected(f"OpenRouter is not configured: {e}") from e

        with self._lock:
            if self._current is not None and self._current.state in ("starting", "running"):
                raise RunRejected(
                    f"run {self._current.id} is already in progress. Only one run at "
                    "a time: an agent run holds this graph's writer lock for its "
                    "whole duration (DESIGN.md §5 principle 7)."
                )
            run = Run(uuid.uuid4().hex[:12], instructions.strip(), agent_id,
                      budget_usd, turns, model)
            self._current = run
            self._history.append(run)

        thread = threading.Thread(
            target=self._execute, args=(run, corpus_scope, method_label),
            name=f"cohort-run-{run.id}", daemon=True,
        )
        thread.start()
        return run.snapshot()

    # --- the worker thread ----------------------------------------------

    def _execute(self, run: Run, corpus_scope: str, method_label: str) -> None:
        """Owns its own Graph and event loop. Every exception is captured onto
        the run rather than raised: this thread has no caller to catch it, and
        a run that died silently would be worse than one that reports why."""
        graph: Graph | None = None
        refusals_before = 0
        try:
            if self.log_path.is_file():
                refusals_before = len(read_refusals(self.log_path))

            graph = Graph.open(self.db_path, self.log_path)

            profile = graph.agent_profile(run.agent_id)
            if profile is None:
                profile = AgentProfile(
                    id=run.agent_id, kind=AgentKind.WORKER,
                    corpus_scope=corpus_scope or "not declared for this run",
                    method_label=method_label or "not declared for this run",
                )
                graph.register_agent(profile, authored_by=run.agent_id)

            def on_call(call: dict) -> None:
                with run._lock:
                    run.spend = {
                        "budget_usd": call["budget"], "spent_usd": call["spent"],
                        "remaining_usd": max(0.0, call["budget"] - call["spent"]),
                        "calls": call["call"],
                        "unpriced_calls": run.spend["unpriced_calls"]
                        + (0 if call["cost_reported"] else 1),
                    }

            transport = self._transport_factory(run.budget_usd, on_call)
            worker = AttestationWorker(
                graph, source=self.source, authored_by=run.agent_id,
                profile=profile, transport=transport,
            )

            with run._lock:
                run.state = "running"

            log = self._run_turns(run, worker)

            with run._lock:
                run.tool_calls = log
                run.state = "stopped" if run._cancel.is_set() else "finished"
        except BudgetExceeded as e:
            with run._lock:
                run.stopped_early = str(e)
                run.state = "finished"
        except Exception as e:  # noqa: BLE001 — nothing upstream can catch this
            with run._lock:
                run.error = f"{type(e).__name__}: {e}"
                run.state = "failed"
        finally:
            if graph is not None:
                try:
                    graph.close()
                except Exception:  # noqa: BLE001, S110 — closing must not mask the real error
                    pass
            # Refusals this run produced. Read after the lock is released so
            # the log is complete, and diffed against the count from before so
            # a pre-existing history is not attributed to this run.
            try:
                if self.log_path.is_file():
                    new = read_refusals(self.log_path)[refusals_before:]
                    with run._lock:
                        run.refusals = [r.model_dump(mode="json") for r in new]
            except Exception:  # noqa: BLE001, S110 — reporting extra, never fatal
                pass
            with run._lock:
                run.ended_at = time.time()
            with self._lock:
                if self._current is run:
                    self._current = None

    def _run_turns(self, run: Run, worker: AttestationWorker) -> list[dict[str, Any]]:
        """Drive the worker's own loop once, reporting progress as it goes.

        The tempting shape — call `run_async(max_turns=1)` in a loop so each
        turn can be observed — is wrong: `run_async` builds its message list
        from scratch on entry, so every call would restart the conversation,
        discard all prior tool results, and pay the model to rediscover them.
        Progress reporting must not change what the agent knows. So the worker
        keeps its single continuous loop and reports outward through
        `on_tool_call`, and cancellation is checked by the same loop between
        turns via `should_stop`.
        """
        def on_tool_call(entry: dict[str, Any]) -> None:
            with run._lock:
                run.tool_calls = [*run.tool_calls, entry]

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                worker.run_async(
                    run.instructions, max_turns=run.max_turns,
                    on_tool_call=on_tool_call,
                    should_stop=run._cancel.is_set,
                )
            )
        finally:
            asyncio.set_event_loop(None)
            loop.close()
