"""Closed vocabulary: nodes, edges, events, dating (design doc §6).

Pydantic v2 models, not dataclasses, because these shapes are the contract an
*agent* has to satisfy — validation at this boundary is what makes a write
machine-checkable, not merely plausible (design doc §5 principle 4).

Closed on purpose: an unlisted vocabulary string is a `ValidationError`
before it ever reaches the write boundary, not a silently-accepted string.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_dict(self) -> dict:
        return self.model_dump()


RESEARCHER = "researcher"


# --- closed vocabulary ------------------------------------------------------

class NodeType(StrEnum):
    WITNESS = "witness"
    PASSAGE = "passage"
    CLAIM = "claim"
    CONJECTURE = "conjecture"
    QUERY = "query"
    DECISION = "decision"


class EdgeType(StrEnum):
    ATTESTS = "attests"
    CONTRADICTS = "contradicts"
    PARALLEL_OF = "parallel_of"
    DESCENDS_FROM = "descends_from"
    QUOTES = "quotes"
    TESTS = "tests"
    SUPERSEDES = "supersedes"
    #: passage -> witness. Added to the vocabulary deliberately (design doc
    #: §11 flags the payload-field version as a weak point to fix in stage
    #: 2; there's no migration cost to building the edge form from day one).
    PART_OF = "part_of"


class NodeStatus(StrEnum):
    PROPOSED = "proposed"
    ATTESTED = "attested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DatingRoute(StrEnum):
    DATED = "dated"
    ATTRIBUTED = "attributed"
    SOURCE_LABEL = "source_label"
    UNKNOWN = "unknown"


AuthorshipAction = Literal[
    "proposed", "attested", "accepted", "rejected", "reopened", "converged"
]


# --- dating (design doc §6) -------------------------------------------------

class Dating(_Model):
    value: str | None = None
    confidence: DatingRoute
    basis: str = Field(min_length=1)

    @field_validator("basis")
    @classmethod
    def _real_sentence(cls, v: str) -> str:
        v = v.strip()
        if len(v.split()) < 3:
            raise ValueError("basis must be a stated sentence, not a label")
        return v


# --- authorship --------------------------------------------------------------
# A field on every node/edge (accumulating, never overwritten), not an edge —
# an `authored_by` edge would duplicate this with no way to keep the two
# consistent (design doc §6).

class Authorship(_Model):
    author: str = Field(min_length=1)
    at: str = Field(default_factory=now)
    action: AuthorshipAction


# --- node payloads -----------------------------------------------------------

class WitnessPayload(_Model):
    canonical_ref: str = Field(min_length=1)
    label: str | None = None
    dating: Dating


class PassagePayload(_Model):
    canonical_ref: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    excerpt: str | None = None


class ClaimPayload(_Model):
    text: str = Field(min_length=1)


class ConjecturePayload(_Model):
    text: str = Field(min_length=1)


class QueryPayload(_Model):
    text: str = Field(min_length=1)


class DecisionPayload(_Model):
    subject_node_id: str = Field(min_length=1)
    verdict: Literal["accepted", "rejected", "reopened"]
    reason: str | None = None


PAYLOAD_BY_TYPE: dict[NodeType, type[_Model]] = {
    NodeType.WITNESS: WitnessPayload,
    NodeType.PASSAGE: PassagePayload,
    NodeType.CLAIM: ClaimPayload,
    NodeType.CONJECTURE: ConjecturePayload,
    NodeType.QUERY: QueryPayload,
    NodeType.DECISION: DecisionPayload,
}


# --- read-return shapes --------------------------------------------------

class Node(_Model):
    id: str
    type: NodeType
    status: NodeStatus = NodeStatus.PROPOSED
    payload: dict
    authorship: list[Authorship] = Field(default_factory=list)
    rejected_reason: str | None = None
    created_seq: int
    updated_seq: int

    def typed_payload(self) -> _Model:
        return PAYLOAD_BY_TYPE[self.type].model_validate(self.payload)


class Edge(_Model):
    id: str
    type: EdgeType
    src: str
    dst: str
    authorship: list[Authorship] = Field(default_factory=list)
    created_seq: int


class IndependentSupport(_Model):
    """design doc §4, §11 — the counter-argument to consensus-seeking."""

    node_id: str
    attesting_count: int
    distinct_witnesses: int
    independent: bool
    non_independent_pairs: list[tuple[str, str]] = Field(default_factory=list)


class RebuildReport(_Model):
    ok: bool
    events_replayed: int
    nodes: int
    edges: int


# --- events (design doc §5 principle 1) -------------------------------------

EVENT_TYPES = {
    "propose", "attest", "accept", "reject", "reopen", "add_edge", "refused",
}


class Event(_Model):
    seq: int
    event: str
    authored_by: str = Field(min_length=1)
    at: str = Field(default_factory=now)
    node_id: str | None = None
    edge_id: str | None = None
    node_type: NodeType | None = None
    edge_type: EdgeType | None = None
    detail: dict = Field(default_factory=dict)

    @field_validator("event")
    @classmethod
    def _known_event(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {v!r}")
        return v
