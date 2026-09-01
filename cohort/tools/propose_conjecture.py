"""propose_conjecture: propose something not yet stated by any source,
together with a dossier and the query that would test it.

The falsifiability gate's write side (design doc §7) is unchanged: a
conjecture proposed any other way has no `tests` edge and is permanently
unattestable via `attests` edges, however many it collects. This tool is
still the only sanctioned way to get a conjecture past that gate.

Layered on top (docs/roadmap.md "Scope revision", verification axis): the
dossier fields (`derivation`, `corpus_boundary`, `selection_risks`,
`alternative_explanations`) are enforced by `ConjecturePayload` itself, at
proposal time, not by a new write-boundary rule — pydantic already refuses
the payload before this tool ever calls `graph.propose_conjecture()`. And a
prior-art search is now required and actually run (not just claimed): this
tool searches the corpus first, records the search as a `query` node with a
`searched_for` edge to the conjecture, distinct from the `tests` edge
(which records what would settle the conjecture going forward, not what was
already searched before proposing it).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..graph import Graph
from ..schemas import ConjecturePayload, EdgeType, QueryPayload
from ..sources.base import Source

NAME = "propose_conjecture"
DESCRIPTION = (
    "Propose a conjecture the sources don't yet state outright. Requires a "
    "full dossier (derivation, corpus boundary, selection risks, "
    "alternative explanations), a prior-art query that is actually run "
    "against the corpus before proposing, and a query that would confirm "
    "or refute the conjecture going forward. A conjecture proposed without "
    "the prospective query cannot be attested."
)


class ProposeConjectureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    derivation: str = Field(min_length=1)
    corpus_boundary: str = Field(min_length=1)
    selection_risks: str = Field(min_length=1)
    alternative_explanations: str = Field(min_length=1)
    prior_art_query: str = Field(min_length=1)
    tests_query_text: str = Field(min_length=1)


def propose_conjecture(
    graph: Graph, source: Source, args: ProposeConjectureInput, *, authored_by: str,
    model_call_id: int | None = None,
) -> str:
    prior_art_hits = source.search(args.prior_art_query)
    prior_art_query_id = graph.propose_query(
        QueryPayload(text=f"prior art: {args.prior_art_query!r} ({len(prior_art_hits)} hits)"),
        authored_by=authored_by, model_call_id=model_call_id,
    )

    conjecture_id = graph.propose_conjecture(
        ConjecturePayload(
            text=args.text,
            derivation=args.derivation,
            corpus_boundary=args.corpus_boundary,
            selection_risks=args.selection_risks,
            alternative_explanations=args.alternative_explanations,
        ),
        authored_by=authored_by, model_call_id=model_call_id,
    )

    graph.add_edge(
        EdgeType.SEARCHED_FOR, prior_art_query_id, conjecture_id, authored_by=authored_by,
        model_call_id=model_call_id,
    )

    tests_query_id = graph.propose_query(
        QueryPayload(text=args.tests_query_text), authored_by=authored_by,
        model_call_id=model_call_id,
    )
    graph.add_edge(
        EdgeType.TESTS, tests_query_id, conjecture_id, authored_by=authored_by,
        model_call_id=model_call_id,
    )
    return conjecture_id
