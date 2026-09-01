"""Append-only JSONL event log — ground truth (design doc §5 principle 1).

Never truncated on open: this log is cumulative across the graph's whole
life, not a per-run trace. Replay is a separate, pure module-level function
that never constructs an `EventLog`, so a rebuild is structurally incapable
of writing a stray file — the specific bug design doc §11 names in a prior
attempt ("rebuild writes a stray replay log because the constructor insists
on one").
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator

from .errors import RefusalCategory, UnknownEventType, refusal_category
from .schemas import (
    EVENT_TYPES,
    EdgeType,
    Event,
    ModelCallSummary,
    NodeType,
    Refusal,
    RefusalCensus,
    RefusalStreak,
)


class EventLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch()
        self._next_seq = _next_seq_after(self.path)

    def append(
        self,
        event: str,
        *,
        authored_by: str,
        node_id: str | None = None,
        edge_id: str | None = None,
        node_type: NodeType | None = None,
        edge_type: EdgeType | None = None,
        detail: dict | None = None,
        model_call_id: int | None = None,
        model: str | None = None,
        provider: str | None = None,
        prompt_version: str | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> Event:
        if event not in EVENT_TYPES:
            raise UnknownEventType(event)
        record = Event(
            seq=self._next_seq,
            event=event,
            authored_by=authored_by,
            node_id=node_id,
            edge_id=edge_id,
            node_type=node_type,
            edge_type=edge_type,
            detail=detail or {},
            model_call_id=model_call_id,
            model=model,
            provider=provider,
            prompt_version=prompt_version,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json())
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        self._next_seq += 1
        return record

    def __len__(self) -> int:
        return self._next_seq


def read_events(path: str | Path) -> Iterator[Event]:
    """Pure read. Never creates the file; never writes."""
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield Event.model_validate_json(line)


def _next_seq_after(path: Path) -> int:
    last = -1
    for ev in read_events(path):
        last = ev.seq
    return last + 1


def summarize_model_calls(path: str | Path) -> ModelCallSummary:
    """Plain arithmetic over the log's "model_call" events — counted, not
    asserted, matching the house habit (design doc §13). A pure log scan,
    not a Graph method: model_call events never touch the SQLite
    projection, so this is a property of the log, not of graph state."""
    calls = 0
    total_input = total_output = total_latency = 0
    total_cost = 0.0
    for ev in read_events(path):
        if ev.event != "model_call":
            continue
        calls += 1
        total_input += ev.input_tokens or 0
        total_output += ev.output_tokens or 0
        total_latency += ev.latency_ms or 0
        total_cost += ev.cost_usd or 0.0
    return ModelCallSummary(
        calls=calls,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_latency_ms=total_latency,
        total_cost_usd=total_cost,
    )


#: A streak needs at least this many consecutive refusals. Two is the lowest
#: number that can mean anything — one refusal is an event, two of the same
#: rule from the same agent is the first point at which "it adapted and was
#: refused again" is even describable.
MIN_STREAK = 2


def summarize_refusals(path: str | Path) -> RefusalCensus:
    """Arithmetic over a log's refused writes — see `RefusalCensus`.

    A pure log scan, like `summarize_model_calls`: a refused write changed no
    graph state, so there is nothing in the SQLite projection to read this
    from. It takes a path rather than a list of `Refusal`s so a caller cannot
    accidentally census a *truncated* view — `read_refusals(limit=n)` returns
    the tail, and a census over the tail would report a smaller total than the
    log holds while looking authoritative.
    """
    refusals = read_refusals(path)
    census = RefusalCensus(
        total=len(refusals),
        by_category={c.value: 0 for c in RefusalCategory},
        first_at=refusals[0].at if refusals else None,
        last_at=refusals[-1].at if refusals else None,
    )
    by_rule: Counter[str] = Counter()
    by_author: Counter[str] = Counter()
    by_attempted: Counter[str] = Counter()
    for r in refusals:
        by_rule[r.rule] += 1
        by_author[r.authored_by] += 1
        by_attempted[r.attempted] += 1
        census.by_category[refusal_category(r.rule).value] += 1

    # Most frequent first, ties broken by name so the output is stable across
    # runs — a census that reordered itself between two reads of one log would
    # be useless for diffing.
    def ranked(counter: Counter[str]) -> dict[str, int]:
        return dict(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))

    census.by_rule = ranked(by_rule)
    census.by_author = ranked(by_author)
    census.by_attempted = ranked(by_attempted)
    census.expression_count = census.by_category[RefusalCategory.EXPRESSION.value]
    census.streaks = _streaks(refusals)
    census.streaked_count = sum(s.count for s in census.streaks)
    return census


def _streaks(refusals: list[Refusal]) -> list[RefusalStreak]:
    """Runs of the same rule within one author's own sequence.

    Grouping by author before looking for runs is what makes this survive a
    swarm: several agents interleave their refusals in one log, and a run
    defined over the raw sequence would be broken by an unrelated agent's
    refusal landing in between — losing the signal exactly when the most
    agents are running.
    """
    by_author: dict[str, list[Refusal]] = defaultdict(list)
    for r in refusals:
        by_author[r.authored_by].append(r)

    streaks: list[RefusalStreak] = []
    for author, theirs in by_author.items():
        run: list[Refusal] = []
        for r in [*theirs, None]:  # a sentinel so the final run is emitted too
            if run and (r is None or r.rule != run[0].rule):
                if len(run) >= MIN_STREAK:
                    streaks.append(
                        RefusalStreak(
                            authored_by=author,
                            rule=run[0].rule,
                            category=refusal_category(run[0].rule).value,
                            count=len(run),
                            first_seq=run[0].seq,
                            last_seq=run[-1].seq,
                            attempted=list(dict.fromkeys(x.attempted for x in run)),
                            node_ids=list(dict.fromkeys(x.node_id for x in run if x.node_id)),
                        )
                    )
                run = []
            if r is not None:
                run.append(r)
    # Longest first: the longest run is the one most likely to be a tool gap
    # rather than a slip, so it is what a reader should meet first.
    streaks.sort(key=lambda s: (-s.count, s.first_seq))
    return streaks


def read_refusals(path: str | Path, *, limit: int | None = None) -> list[Refusal]:
    """Every refused write in the log, oldest first — a pure log scan, same
    pattern as `summarize_model_calls`.

    This exists because a refusal is an output of this system, not a
    diagnostic (docs/design.md §15). Before it, the only way to see refusals was
    an ad-hoc list comprehension over `read_events` in `demo.py`, which meant
    the most distinctive thing COHORT does was visible in terminal output and
    nowhere else.

    A log scan rather than a `Graph` method on purpose: a refused write, by
    definition, changed no graph state, so there is nothing in the SQLite
    projection to read it from. `limit` keeps the *most recent* n (the tail),
    since that is what a reader actually wants when a log has grown long.
    """
    refusals = [
        Refusal(
            seq=ev.seq,
            at=ev.at,
            authored_by=ev.authored_by,
            attempted=ev.detail.get("attempted", "unknown"),
            rule=ev.detail.get("rule", "unknown"),
            message=ev.detail.get("message", ""),
            node_id=ev.node_id,
            edge_id=ev.edge_id,
            node_type=ev.node_type,
            edge_type=ev.edge_type,
            model_call_id=ev.model_call_id,
        )
        for ev in read_events(path)
        if ev.event == "refused"
    ]
    return refusals[-limit:] if limit is not None else refusals
