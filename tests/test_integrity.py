"""Independent payload-integrity hashing (ROADMAP.md "Scope revision",
integrity-hashing workstream). `verify_integrity()` is an explicit, on-demand
check — never an ambient hazard on every read, same posture as `rebuild()`.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cohort.schemas import (
    ClaimPayload,
    Dating,
    DatingRoute,
    PassagePayload,
    VerificationResult,
    WitnessPayload,
)
from cohort.sources.base import SourceRecord
from cohort.sources.local_reader import LocalReader
from cohort.tools.find_attestations import FindAttestationsInput, find_attestations
from cohort.tools.verify_exact_span import verify_exact_span

AGENT = "agent:worker-1"
FIXTURE = Path(__file__).parent.parent / "examples" / "local_corpus"


@pytest.fixture
def source():
    r = LocalReader(FIXTURE)
    yield r
    r.close()


def _dating():
    return Dating(confidence=DatingRoute.UNKNOWN, basis="not dated for this test")


def test_payload_hash_is_recorded_on_propose(graph):
    claim_id = graph.propose_claim(ClaimPayload(text="a claim"), authored_by=AGENT)
    row = graph.conn.execute(
        "SELECT payload, payload_hash FROM nodes WHERE id=?", (claim_id,)
    ).fetchone()
    assert row["payload_hash"] is not None
    assert row["payload_hash"] == hashlib.sha256(row["payload"].encode("utf-8")).hexdigest()


def test_verify_integrity_is_clean_on_an_untouched_graph(graph):
    graph.propose_claim(ClaimPayload(text="claim A"), authored_by=AGENT)
    graph.propose_claim(ClaimPayload(text="claim B"), authored_by=AGENT)
    report = graph.verify_integrity()
    assert report.checked == 2
    assert report.mismatched == []
    assert report.unhashed == []


def test_verify_integrity_detects_a_hand_corrupted_row(graph):
    claim_id = graph.propose_claim(ClaimPayload(text="a claim"), authored_by=AGENT)
    graph.conn.execute(
        "UPDATE nodes SET payload=? WHERE id=?",
        ('{"text": "tampered"}', claim_id),
    )
    graph.conn.commit()
    report = graph.verify_integrity()
    assert report.mismatched == [claim_id]


def test_verify_integrity_scopes_to_a_single_node(graph):
    c1 = graph.propose_claim(ClaimPayload(text="claim A"), authored_by=AGENT)
    graph.propose_claim(ClaimPayload(text="claim B"), authored_by=AGENT)
    graph.conn.execute("UPDATE nodes SET payload=? WHERE id=?", ('{"text": "tampered"}', c1))
    graph.conn.commit()

    report = graph.verify_integrity(c1)
    assert report.checked == 1
    assert report.mismatched == [c1]


def test_verify_integrity_reports_unhashed_rows_from_before_the_column_existed(graph):
    graph.conn.execute(
        "INSERT INTO nodes (id, type, status, payload, created_seq, updated_seq) "
        "VALUES ('claim:legacy', 'claim', 'proposed', '{\"text\": \"pre-hashing row\"}', 0, 0)"
    )
    graph.conn.commit()
    report = graph.verify_integrity("claim:legacy")
    assert report.unhashed == ["claim:legacy"]
    assert report.mismatched == []


# --- verify_exact_span: the hash-chain re-verifier (design doc §4, §7) ------

class _FakeSource:
    """A minimal Source test double whose fetched text can be mutated
    between calls, so drift-detection can be tested without touching real
    files on disk."""

    source_name = "fake"
    access_mode = "test"

    def __init__(self, texts: dict[str, str]):
        self.texts = texts

    def search(self, query, max_results=20):
        return []

    def fetch(self, ref):
        return SourceRecord(ref=ref, title=ref, text=self.texts[ref], witness_ref="fake:w1")


def test_verify_exact_span_passes_against_a_real_source(graph, source):
    claim_id = graph.propose_claim(ClaimPayload(text="a claim about the moon"), authored_by=AGENT)
    passage_ids = find_attestations(
        graph, source, FindAttestationsInput(claim_or_conjecture_id=claim_id, query="明月"),
        authored_by=AGENT,
    )
    verification_id = verify_exact_span(graph, source, passage_ids[0], authored_by=AGENT)
    node = graph.get_node(verification_id)
    assert node.payload["result"] == VerificationResult.PASS
    assert node.payload["span_start"] is not None


def test_verify_exact_span_indeterminate_without_source_ref_or_excerpt(graph):
    witness_id = graph.propose_witness(
        WitnessPayload(canonical_ref="T01n0001", dating=_dating()),
        authored_by=AGENT,
    )
    passage_id = graph.propose_passage(
        PassagePayload(canonical_ref="T01n0001p0001", locator="juan 1"),  # no excerpt, no source_ref
        witness_id=witness_id, authored_by=AGENT,
    )
    fake = _FakeSource({})
    verification_id = verify_exact_span(graph, fake, passage_id, authored_by=AGENT)
    assert graph.get_node(verification_id).payload["result"] == VerificationResult.INDETERMINATE


def test_verify_exact_span_matches_the_prior_recorded_location_on_reverification(graph):
    fake = _FakeSource({"w1.txt": "the quick brown fox jumps"})
    witness_id = graph.propose_witness(
        WitnessPayload(
            canonical_ref="fake:w1",
            dating=_dating(),
        ),
        authored_by=AGENT,
    )
    passage_id = graph.propose_passage(
        PassagePayload(
            canonical_ref="fake:w1#p1", locator="line 1", excerpt="quick brown fox",
            source_ref="w1.txt",
        ),
        witness_id=witness_id, authored_by=AGENT,
    )
    first = graph.get_node(verify_exact_span(graph, fake, passage_id, authored_by=AGENT))
    second = graph.get_node(verify_exact_span(graph, fake, passage_id, authored_by=AGENT))
    assert first.payload["result"] == VerificationResult.PASS
    assert second.payload["result"] == VerificationResult.PASS
    assert first.payload["span_start"] == second.payload["span_start"]


def test_verify_exact_span_fails_when_the_source_changes(graph):
    fake = _FakeSource({"w1.txt": "the quick brown fox jumps"})
    witness_id = graph.propose_witness(
        WitnessPayload(canonical_ref="fake:w1", dating=_dating()), authored_by=AGENT,
    )
    passage_id = graph.propose_passage(
        PassagePayload(
            canonical_ref="fake:w1#p1", locator="line 1", excerpt="quick brown fox",
            source_ref="w1.txt",
        ),
        witness_id=witness_id, authored_by=AGENT,
    )
    verify_exact_span(graph, fake, passage_id, authored_by=AGENT)  # establishes the baseline

    fake.texts["w1.txt"] = "a completely different sentence, but it still has quick brown fox in it somewhere"
    second = graph.get_node(verify_exact_span(graph, fake, passage_id, authored_by=AGENT))
    assert second.payload["result"] == VerificationResult.FAIL
