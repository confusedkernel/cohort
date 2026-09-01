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
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A3_EDITION_SUPPORT_CHECKED,
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
        result=VerificationResult.FAIL, assurance_level=AssuranceLevel.A3_EDITION_SUPPORT_CHECKED,
        detail="the apparatus for this witness could not be read",
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
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A3_EDITION_SUPPORT_CHECKED,
        detail="four edition families collated", authored_by=AGENT,
    )
    assert graph.assurance_for(claim_id) == AssuranceLevel.A3_EDITION_SUPPORT_CHECKED


def test_a_later_failure_lowers_the_assurance_its_pass_granted(graph):
    """The bug this guards: `assurance_for` took the maximum over every
    passing verification, so a stale PASS outranked a later FAIL forever. A
    passage verified at A2 whose excerpt then *moved in the source* still read
    `A2_EXACT_SPAN_MATCHED` — `verify_exact_span` detected the move, recorded
    the failure, and the summary ignored it. Passing review while proving
    nothing, which is the failure that tool's own docstring guards against
    internally."""
    claim_id = _claim(graph)
    graph.verify(
        claim_id, method=VerificationMethod.EXACT_SPAN,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A2_EXACT_SPAN_MATCHED,
        detail="matched at the recorded span", authored_by=AGENT,
    )
    assert graph.assurance_for(claim_id) == AssuranceLevel.A2_EXACT_SPAN_MATCHED

    graph.verify(
        claim_id, method=VerificationMethod.EXACT_SPAN,
        result=VerificationResult.FAIL, assurance_level=AssuranceLevel.A0_UNCHECKED,
        detail="excerpt moved or changed since the last recorded verification",
        authored_by=AGENT,
    )
    assert graph.assurance_for(claim_id) == AssuranceLevel.A0_UNCHECKED
    # nothing was deleted: the summary changed, the record did not
    assert len(graph.verifications(claim_id)) == 2


def test_a_different_method_does_not_erase_a_standing_result(graph):
    """Latest-*per-method*, not latest overall. Different methods establish
    different things and a node holds several at once, so a later collation
    must not withdraw a standing exact-span result — only the same check,
    re-run with a different answer, supersedes itself."""
    claim_id = _claim(graph)
    graph.verify(
        claim_id, method=VerificationMethod.EXACT_SPAN,
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A2_EXACT_SPAN_MATCHED,
        detail="matched at the recorded span", authored_by=AGENT,
    )
    graph.verify(
        claim_id, method=VerificationMethod.CROSS_EDITION_COLLATION,
        result=VerificationResult.FAIL, assurance_level=AssuranceLevel.A0_UNCHECKED,
        detail="no apparatus in this witness", authored_by=AGENT,
    )
    assert graph.assurance_for(claim_id) == AssuranceLevel.A2_EXACT_SPAN_MATCHED


def test_re_verifying_restores_what_a_failure_withdrew(graph):
    """The other direction: a check that fails and later passes again is
    current again. Assurance is the node's standing now, not a high-water
    mark and not a permanent mark against it."""
    claim_id = _claim(graph)
    for result, level in (
        (VerificationResult.PASS, AssuranceLevel.A2_EXACT_SPAN_MATCHED),
        (VerificationResult.FAIL, AssuranceLevel.A0_UNCHECKED),
        (VerificationResult.PASS, AssuranceLevel.A2_EXACT_SPAN_MATCHED),
    ):
        graph.verify(
            claim_id, method=VerificationMethod.EXACT_SPAN, result=result,
            assurance_level=level, detail="re-checked", authored_by=AGENT,
        )
    assert graph.assurance_for(claim_id) == AssuranceLevel.A2_EXACT_SPAN_MATCHED


def test_the_pre_rename_assurance_string_still_reads(graph):
    """The event log is ground truth and is never rewritten, so a graph seeded
    before A3 was renamed holds the old string in its payloads and its log.
    Rewriting those would break the payload hashes `verify_integrity()` checks,
    or make `rebuild()` disagree with the log — so the old name is read and
    never written."""
    assert AssuranceLevel("A3_INDEPENDENCE_CHECKED") is AssuranceLevel.A3_EDITION_SUPPORT_CHECKED


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
        result=VerificationResult.PASS, assurance_level=AssuranceLevel.A3_EDITION_SUPPORT_CHECKED,
        detail="n/a", limitations="single-witness sample", authored_by=AGENT,
    )
    report = g.rebuild()
    assert report.ok is True
    g.close()
