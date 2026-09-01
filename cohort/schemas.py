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
    #: one verification attempt against a claim/conjecture/passage/witness.
    #: Parallel to `decision`: a record of a judgement, not evidential
    #: content itself (ROADMAP.md "Scope revision", verification axis).
    VERIFICATION = "verification"


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
    #: verification -> {claim, conjecture, passage, witness}. The evidentiary
    #: node points at what it evidences, same direction as `attests`/`tests`.
    VERIFIES = "verifies"
    #: query -> conjecture. Records that a prior-art search was actually run
    #: before a conjecture was proposed, distinct from `tests` (which records
    #: what would settle the conjecture going forward, not what was already
    #: searched for before proposing it).
    SEARCHED_FOR = "searched_for"


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


class AssuranceLevel(StrEnum):
    """A computed read over a node's `verifies`-linked verification nodes
    (`Graph.assurance_for()`), never a second mutable field on the subject
    node — the graph is a projection, and a stored assurance field could
    drift from the verification nodes it's supposed to summarize (design doc
    §5 principle 1). Orthogonal to `NodeStatus`: a claim can be `accepted`
    with no verification ever run, or `proposed` with several. StrEnum
    values are stable strings so a later rung can be inserted without
    renumbering or touching already-recorded verification nodes."""

    A0_UNCHECKED = "A0_UNCHECKED"
    A1_LOCATOR_VALID = "A1_LOCATOR_VALID"
    A2_EXACT_SPAN_MATCHED = "A2_EXACT_SPAN_MATCHED"
    A3_INDEPENDENCE_CHECKED = "A3_INDEPENDENCE_CHECKED"
    A4_HUMAN_APPROVED = "A4_HUMAN_APPROVED"


class VerificationMethod(StrEnum):
    """Domain-appropriate mechanical checks only — no numerical/statistical/
    code/database verifiers (no such claims exist in a philological corpus),
    and deliberately no MODEL_ENTAILMENT: a second model's opinion is still
    another agent's opinion, and admitting it as a formal verification
    method would smuggle consensus-among-models back in through the side
    door (design doc §4's whole thesis)."""

    LOCATOR_RESOLUTION = "locator_resolution"
    EXACT_SPAN = "exact_span"
    CROSS_EDITION_COLLATION = "cross_edition_collation"
    DATING_ROUTE_CONFIDENCE = "dating_route_confidence"
    HUMAN_REVIEW = "human_review"


class VerificationResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


AuthorshipAction = Literal[
    "proposed", "attested", "accepted", "rejected", "reopened", "converged"
]


class AgentKind(StrEnum):
    WORKER = "worker"
    RESEARCHER = "researcher"


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


# --- agent identity (sidecar, not a graph node) -----------------------------
# An agent's declared corpus/method scope is operational metadata about a
# writer, not evidence about the corpus — principle 2 makes it a category
# error inside the closed node/edge vocabulary. Lives in a sidecar `agents`
# table, same footing as `node_authorship`/`edge_authorship` (ROADMAP.md
# "Scope revision", agent-society axis).

class AgentProfile(_Model):
    id: str = Field(min_length=1)
    kind: AgentKind
    corpus_scope: str | None = None
    method_label: str | None = None


class AgentReport(_Model):
    """A pure contribution-history count, never a score. Deliberately not a
    reputation number: outcome-based signals that could feed one (ladder
    survival rate, independence quality, discount-edge contribution,
    responsiveness after rejection) are follow-on work, not built here — see
    ROADMAP.md. This report must never be consulted by a write-boundary
    method; a number here feeding back into `attest()`/`accept()` would
    violate principle 6 by the back door."""

    agent_id: str
    proposed: int
    attested: int
    accepted: int
    rejected: int
    discount_edges_contributed: int


# --- node payloads -----------------------------------------------------------

class WitnessPayload(_Model):
    canonical_ref: str = Field(min_length=1)
    label: str | None = None
    dating: Dating
    #: license/rights terms for a restrictively-licensed but locally-held
    #: source (e.g. CBETA — CC BY-NC-SA-equivalent, not public domain).
    #: Additive; a single descriptive string is deliberate, not a
    #: structured rights model — DESIGN.md §2 forbids COHORT from building a
    #: governance layer, even a small one (ROADMAP.md "Scope revision").
    source_terms: str | None = None


class PassagePayload(_Model):
    canonical_ref: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    excerpt: str | None = None
    #: how to re-fetch this passage's source for re-verification (e.g. a
    #: CbetaReader ref string). Additive; existing passages have none.
    source_ref: str | None = None


class ClaimPayload(_Model):
    text: str = Field(min_length=1)


class ConjecturePayload(_Model):
    """The falsifiability gate's own check (design doc §7, `attest()`'s
    conjecture branch) is untouched by the dossier below — it still asks
    only for a `tests` edge. These four fields are the *richer* dossier
    (ROADMAP.md "Scope revision"), enforced by pydantic at proposal time,
    not by a new write-boundary rule. "none identified" is a legitimate
    value for the risk/alternatives fields, same pattern as `Dating.basis`:
    declining is legitimate, silence isn't."""

    text: str = Field(min_length=1)
    derivation: str = Field(min_length=1)
    corpus_boundary: str = Field(min_length=1)
    selection_risks: str = Field(min_length=1)
    alternative_explanations: str = Field(min_length=1)


class QueryPayload(_Model):
    text: str = Field(min_length=1)


class DecisionPayload(_Model):
    subject_node_id: str = Field(min_length=1)
    verdict: Literal["accepted", "rejected", "reopened"]
    reason: str | None = None


class VerificationPayload(_Model):
    method: VerificationMethod
    result: VerificationResult
    assurance_level: AssuranceLevel
    detail: str = Field(min_length=1)
    limitations: str | None = None
    #: the hash chain for an EXACT_SPAN check: hash of the whole fetched
    #: source text, hash of the located excerpt, and the span it was found
    #: at. Additive; only EXACT_SPAN verifications populate these. The unit
    #: is reader-dependent, not always bytes: a `Source` that returns
    #: decoded `str` (the general case) yields character offsets from
    #: `str.find()`; a reader operating on raw bytes (e.g. CBETA's archive
    #: reader) yields true byte offsets. Named span_*, not byte_*, so the
    #: field name doesn't overclaim a precision the generic case can't give.
    source_hash: str | None = None
    excerpt_hash: str | None = None
    span_start: int | None = None
    span_end: int | None = None


PAYLOAD_BY_TYPE: dict[NodeType, type[_Model]] = {
    NodeType.WITNESS: WitnessPayload,
    NodeType.PASSAGE: PassagePayload,
    NodeType.CLAIM: ClaimPayload,
    NodeType.CONJECTURE: ConjecturePayload,
    NodeType.QUERY: QueryPayload,
    NodeType.DECISION: DecisionPayload,
    NodeType.VERIFICATION: VerificationPayload,
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
    #: why this edge was drawn. Optional because most edge types carry their
    #: meaning in the type plus their endpoints; required in practice for
    #: `contradicts`, which `record_contradiction` will not write without one
    #: (see that tool for the argument).
    reason: str | None = None


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


class IntegrityReport(_Model):
    """An explicit, on-demand check (`Graph.verify_integrity()`), never an
    ambient hazard on every read — one tampered row must not turn every
    future `get_node()`/`citable()` call touching it into a crash. Symmetrical
    with `RebuildReport`: something you call to check, not something that
    silently gates reads."""

    checked: int
    mismatched: list[str] = Field(default_factory=list)
    unhashed: list[str] = Field(default_factory=list)


# --- events (design doc §5 principle 1) -------------------------------------
#
# "model_call" is a non-mutating audit marker, exactly like "refused" —
# _apply() treats it as a no-op. It's a dedicated event rather than metadata
# bolted onto every write it causes because the relationship is many-to-one:
# one API response can drive several tool calls, each producing several
# graph writes, and duplicating latency/cost across all of them would
# double-count it. Each write event instead carries model_call_id, pointing
# back at the model_call event's own seq.

EVENT_TYPES = {
    "propose", "attest", "accept", "reject", "reopen", "add_edge", "refused",
    "model_call", "verify", "register_agent",
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

    #: observability envelope — all optional so every event logged before
    #: this addition, and every event with nothing to report, replays
    #: identically. Set on "model_call" events; write events that a model
    #: call caused carry only model_call_id, pointing back at that event's seq.
    model_call_id: int | None = None
    model: str | None = None
    provider: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None

    @field_validator("event")
    @classmethod
    def _known_event(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {v!r}")
        return v


class Refusal(_Model):
    """One refused write, read back out of the log.

    Refusals are part of the scholarly output (DESIGN.md §15: "whose
    refusals are part of its scholarly output"), not error telemetry, so
    they get a real read model rather than being reassembled from raw
    `detail` dicts at every call site. `rule` is the exception class name —
    the rule the design claims, named in `errors.py` — which is what makes a
    refusal legible as "the system declined, and here is which commitment
    made it decline".

    Deliberately a projection of the log rather than a row in SQLite: a
    refusal never changed graph state, so storing it in the projection would
    put something in there that `nodes`/`edges` cannot account for.
    """

    seq: int
    at: str
    authored_by: str
    #: the write that was attempted: "propose", "attest", "accept", "add_edge", ...
    attempted: str
    #: the `errors.py` class name of the rule that refused it
    rule: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None
    node_type: NodeType | None = None
    edge_type: EdgeType | None = None
    #: set when a model call caused the refused write, pointing at its event seq
    model_call_id: int | None = None


class ModelCallSummary(_Model):
    calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: int
    total_cost_usd: float
