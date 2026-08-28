"""find_attestations: search the corpus for passages relevant to a claim or
conjecture, and record each match as an `attests` edge.

Each hit becomes a `witness` (converging with any existing one for the same
`witness_ref`), a `passage` located within it via `part_of`, and an
`attests` edge to the target. The passage is attested immediately — "the
passage exists, the citation resolves, the reference is well formed" is
exactly the mechanical check an agent may perform (design doc §8) — which is
what lets a claim become attestable once enough passages back it.

The witness is proposed with `DatingRoute.UNKNOWN`, not left undated: this
tool has no dating information from the corpus, and declining to date
something is a legitimate answer that still owes a reason (design doc §6).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..graph import Graph
from ..schemas import (
    Dating,
    DatingRoute,
    EdgeType,
    NodeStatus,
    NodeType,
    PassagePayload,
    WitnessPayload,
)
from ..sources.base import Source

NAME = "find_attestations"
DESCRIPTION = (
    "Search the corpus for passages relevant to a claim or conjecture and "
    "record each match as an attests edge, backed by a newly-or-already "
    "recorded witness and passage."
)


class FindAttestationsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_or_conjecture_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)


def find_attestations(
    graph: Graph, source: Source, args: FindAttestationsInput, *, authored_by: str
) -> list[str]:
    target = graph.get_node(args.claim_or_conjecture_id)
    if target.type not in (NodeType.CLAIM, NodeType.CONJECTURE):
        raise ValueError(
            f"{args.claim_or_conjecture_id} is a {target.type}, not a claim or conjecture"
        )

    passage_ids: list[str] = []
    for hit in source.search(args.query, max_results=args.max_results):
        record = source.fetch(hit.ref)

        witness_id = graph.propose_witness(
            WitnessPayload(
                canonical_ref=record.witness_ref,
                label=record.title,
                dating=Dating(
                    confidence=DatingRoute.UNKNOWN,
                    basis="not yet dated by this worker; no dating route run",
                ),
            ),
            authored_by=authored_by,
        )

        passage_id = graph.propose_passage(
            PassagePayload(
                canonical_ref=f"{record.witness_ref}#{hit.ref}",
                locator=record.locator or hit.ref,
                excerpt=hit.snippet,
            ),
            witness_id=witness_id,
            authored_by=authored_by,
        )

        if graph.get_node(passage_id).status == NodeStatus.PROPOSED:
            graph.attest(passage_id, authored_by=authored_by)

        graph.add_edge(
            EdgeType.ATTESTS, passage_id, args.claim_or_conjecture_id, authored_by=authored_by
        )
        passage_ids.append(passage_id)

    return passage_ids
