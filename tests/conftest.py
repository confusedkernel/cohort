"""Shared fixtures for the MEEP test suite."""
from __future__ import annotations

import pytest

from meep.eventlog import EventLog
from meep.graph import Graph

AGENT = "agent:worker-1"
AGENT_2 = "agent:worker-2"


@pytest.fixture
def graph(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    g = Graph(tmp_path / "graph.sqlite", event_log=log)
    yield g
    g.close()
