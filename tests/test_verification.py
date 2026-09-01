"""The verification/assurance model (docs/roadmap.md "Scope revision"): a
verification node is a record of a judgement, not evidential content, same
footing as `decision`. `assurance_for()` is a computed read over passing
verification nodes, never a second mutable field on the subject.
"""
from __future__ import annotations

import pytest

from cohort.errors import EdgeDomainViolation, NotResearcher
from cohort.eventlog import EventLog
from cohort.graph import Graph
from cohort.schemas import (
    RESEARCHER,
    AssuranceLevel,
    ClaimPayload,
    Dating,
    DatingRoute,
    EdgeType,
    NodeStatus,
    PassagePayload,
    VerificationMethod,
    VerificationResult,
    WitnessPayload,
)

AGENT = "agent:worker-1"
#: A second agent, because an agent may not attest what it authored
#: (`Graph._reviewer_conflict`). Unregistered on purpose in most of
#: these fixtures: with no declared model there is no family to
#: compare, so what is being exercised is the author-is-not-reviewer
#: half of the rule on its own.
REVIEWER = "agent:reviewer-1"


def _witness(g, ref="T01n0001", *, confidence=DatingRoute.SOURCE_LABEL, authored_by=AGENT):
    return g.propose_witness(
        WitnessPayload(
            canonical_ref=ref,
            dating=Dating(confidence=confidence, basis="colophon states a Northern Song printing"),
        ),
        authored_by=authored_by,
    )


def _claim(g, text="a claim", *, authored_by=AGENT):
    return g.propose_claim(ClaimPayload(text=text), authored_by=authored_by)


def test_verify_creates_a_verification_node_born_accepted(graph):
    claim_id = _claim(graph)
    verification_id = graph.verify(
        claim_id, method=VerificationMethod.CROSS_EDITION_COLLATION,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A3_INDEPENDENCE_CHECKED,
        detail="no attesting passages yet, so trivially independent", authored_by=AGENT,
    )
    node = graph.get_node(verification_id)
    assert node.type == "verification"
    assert node.status == NodeStatus.ACCEPTED  # bypasses the ladder, like decision


def test_verify_links_a_verifies_edge_to_the_subject(graph):
    claim_id = _claim(graph)
    graph.verify(
        claim_id, method=VerificationMethod.DATING_ROUTE_CONFIDENCE,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A1_LOCATOR_VALID,
        detail="n/a", authored_by=AGENT,
    )
    verifications = graph.verifications(claim_id)
    assert len(verifications) == 1
    assert verifications[0].payload["method"] == "dating_route_confidence"


def test_verify_refuses_an_ineligible_subject_type(graph):
    claim_id = _claim(graph)
    decision_id = graph.reject(claim_id, authored_by=RESEARCHER, reason="unsupported")
    with pytest.raises(EdgeDomainViolation):
        graph.verify(
            decision_id, method=VerificationMethod.HUMAN_REVIEW,
            result=VerificationResult.PASS, assurance_level=AssuranceLevel.A4_HUMAN_APPROVED,
            detail="n/a", authored_by=RESEARCHER,
        )


def test_verify_human_review_requires_the_researcher(graph):
    claim_id = _claim(graph)
    with pytest.raises(NotResearcher):
        graph.verify(
            claim_id, method=VerificationMethod.HUMAN_REVIEW,
            result=VerificationResult.PASS, assurance_level=AssuranceLevel.A4_HUMAN_APPROVED,
            detail="n/a", authored_by=AGENT,
        )


def test_assurance_for_is_a0_with_no_verifications(graph):
    claim_id = _claim(graph)
    assert graph.assurance_for(claim_id) == AssuranceLevel.A0_UNCHECKED


def test_assurance_for_ignores_failing_and_indeterminate_results(graph):
    claim_id = _claim(graph)
    graph.verify(
        claim_id, method=VerificationMethod.CROSS_EDITION_COLLATION,
        result=VerificationResult.FAIL, assurance_level=AssuranceLevel.A3_INDEPENDENCE_CHECKED,
        detail="two attesting witnesses turned out to be in a copying relation",
        authored_by=AGENT,
    )
    graph.verify(
        claim_id, method=VerificationMethod.EXACT_SPAN,
        result=VerificationResult.INDETERMINATE, assurance_level=AssuranceLevel.A2_EXACT_SPAN_MATCHED,
        detail="source text unavailable to check against", authored_by=AGENT,
    )
    assert graph.assurance_for(claim_id) == AssuranceLevel.A0_UNCHECKED


def test_assurance_for_picks_the_highest_passing_level(graph):
    claim_id = _claim(graph)
    graph.verify(
        claim_id, method=VerificationMethod.DATING_ROUTE_CONFIDENCE,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A1_LOCATOR_VALID,
        detail="n/a", authored_by=AGENT,
    )
    graph.verify(
        claim_id, method=VerificationMethod.CROSS_EDITION_COLLATION,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A3_INDEPENDENCE_CHECKED,
        detail="independent_support: independent=True", authored_by=AGENT,
    )
    assert graph.assurance_for(claim_id) == AssuranceLevel.A3_INDEPENDENCE_CHECKED


def test_citable_excludes_verification_nodes(graph):
    claim_id = _claim(graph)
    w = _witness(graph)
    graph.attest(w, authored_by=AGENT)
    p = graph.propose_passage(
        PassagePayload(canonical_ref="T01n0001p0001a12", locator="juan 1"),
        witness_id=w, authored_by=AGENT,
    )
    graph.attest(p, authored_by=AGENT)
    graph.add_edge(EdgeType.ATTESTS, p, claim_id, authored_by=AGENT)
    graph.attest(claim_id, authored_by=REVIEWER)
    graph.accept(claim_id, authored_by=RESEARCHER)
    graph.verify(
        claim_id, method=VerificationMethod.DATING_ROUTE_CONFIDENCE,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A1_LOCATOR_VALID,
        detail="n/a", authored_by=AGENT,
    )
    assert all(n.type != "verification" for n in graph.citable())


def test_rebuild_matches_live_with_verification_events_present(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    g = Graph(tmp_path / "graph.sqlite", event_log=log)
    claim_id = _claim(g)
    g.verify(
        claim_id, method=VerificationMethod.CROSS_EDITION_COLLATION,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A3_INDEPENDENCE_CHECKED,
        detail="n/a", limitations="single-witness sample", authored_by=AGENT,
    )
    report = g.rebuild()
    assert report.ok is True
    g.close()
