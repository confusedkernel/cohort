"""propose_conjecture: propose something not yet stated by any source,
together with the query that would test it.

This is the falsifiability gate's write side (design doc §7): a conjecture
proposed any other way has no `tests` edge and is permanently unattestable
via `attests` edges, however many it collects. This tool is the only
sanctioned way for an agent to get a conjecture past that gate at all —
`propose_conjecture` + `propose_query` + `tests` edge, atomically, from one
tool call.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..graph import Graph
from ..schemas import ConjecturePayload, EdgeType, QueryPayload

NAME = "propose_conjecture"
DESCRIPTION = (
    "Propose a conjecture the sources don't yet state outright, together "
    "with a query that would confirm or refute it. A conjecture proposed "
    "without such a query cannot be attested."
)


class ProposeConjectureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    tests_query_text: str = Field(min_length=1)


def propose_conjecture(graph: Graph, args: ProposeConjectureInput, *, authored_by: str) -> str:
    conjecture_id = graph.propose_conjecture(
        ConjecturePayload(text=args.text), authored_by=authored_by
    )
    query_id = graph.propose_query(
        QueryPayload(text=args.tests_query_text), authored_by=authored_by
    )
    graph.add_edge(EdgeType.TESTS, query_id, conjecture_id, authored_by=authored_by)
    return conjecture_id
