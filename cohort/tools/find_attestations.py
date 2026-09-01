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
    "recorded witness and passage. Returns the passage ids it recorded and "
    "the witness ids they sit in — pass those witness ids to link_parallels "
    "or collate_editions; never construct an id yourself."
)


class FindAttestationsReport(BaseModel):
    """What was recorded, in the ids a caller will need next.

    This used to return a bare `list[str]` of passage ids. A live two-agent run
    showed why that was not enough: `link_parallels` and `collate_editions`
    take a *witness* id, and an agent that had just called this tool had no way
    to obtain one — so it guessed four times in a row
    (`B01n0001`, `B01n0001_002`, the passage id, …), was refused each time, and
    only then found `witness:B01n0001`. Every one of those refusals was correct
    and none of them was avoidable, which makes it a gap in this tool rather
    than a mistake by the model — the same shape as the missing
    `propose_claim`.

    `witnesses` is deduplicated and parallel in meaning to `passages`, not a
    derived convenience: several hits routinely land in one witness.
    """

    model_config = ConfigDict(extra="forbid")

    #: passage ids recorded and attested by this call, in hit order
    passages: list[str] = Field(default_factory=list)
    #: the distinct witnesses those passages sit in — what the stage-4 tools take
    witnesses: list[str] = Field(default_factory=list)


class FindAttestationsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_or_conjecture_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)


def find_attestations(
    graph: Graph, source: Source, args: FindAttestationsInput, *, authored_by: str,
    model_call_id: int | None = None,
) -> FindAttestationsReport:
    target = graph.get_node(args.claim_or_conjecture_id)
    if target.type not in (NodeType.CLAIM, NodeType.CONJECTURE):
        raise ValueError(
            f"{args.claim_or_conjecture_id} is a {target.type}, not a claim or conjecture"
        )

    passage_ids: list[str] = []
    witness_ids: list[str] = []
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
                source_terms=record.note,
            ),
            authored_by=authored_by, model_call_id=model_call_id,
        )
        if witness_id not in witness_ids:
            witness_ids.append(witness_id)

        passage_id = graph.propose_passage(
            PassagePayload(
                canonical_ref=f"{record.witness_ref}#{hit.ref}",
                locator=record.locator or hit.ref,
                excerpt=hit.snippet,
                source_ref=hit.ref,  # lets verify_exact_span re-fetch this exact record later
            ),
            witness_id=witness_id,
            authored_by=authored_by, model_call_id=model_call_id,
        )

        if graph.get_node(passage_id).status == NodeStatus.PROPOSED:
            graph.attest(passage_id, authored_by=authored_by, model_call_id=model_call_id)

        graph.add_edge(
            EdgeType.ATTESTS, passage_id, args.claim_or_conjecture_id, authored_by=authored_by,
            model_call_id=model_call_id,
        )
        passage_ids.append(passage_id)

    return FindAttestationsReport(passages=passage_ids, witnesses=witness_ids)
