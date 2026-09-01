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
from pathlib import Path
from typing import Iterator

from .errors import UnknownEventType
from .schemas import EVENT_TYPES, EdgeType, Event, ModelCallSummary, NodeType, Refusal


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
