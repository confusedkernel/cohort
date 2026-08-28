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
from .schemas import EVENT_TYPES, EdgeType, Event, NodeType


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
