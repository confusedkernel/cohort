"""The stage-2 tools: propose_claim, find_attestations and
propose_conjecture, exercised against the write boundary and the
local_corpus fixture."""
from __future__ import annotations

from pathlib import Path

import pytest

from cohort.errors import UnattestableClaim, UnattestableConjecture
from cohort.schemas import (
    ClaimPayload,
    ConjecturePayload,
    Dating,
    DatingRoute,
    EdgeType,
    NodeStatus,
    WitnessPayload,
)
from cohort.sources.cbeta_reader import CbetaReader
from cohort.sources.local_reader import LocalReader
from cohort.tools.find_attestations import FindAttestationsInput, find_attestations
from cohort.tools.propose_claim import ProposeClaimInput, propose_claim
from cohort.tools.propose_conjecture import ProposeConjectureInput, propose_conjecture

AGENT = "agent:worker-1"
FIXTURE = Path(__file__).parent.parent / "examples" / "local_corpus"


@pytest.fixture
def source():
    r = LocalReader(FIXTURE)
    yield r
    r.close()


def test_find_attestations_locates_and_attests_a_matching_passage(graph, source):
    claim_id = graph.propose_claim(
        ClaimPayload(text="The moon appears in Tang poetry as a figure for homesickness"),
        authored_by=AGENT,
    )
    passage_ids = find_attestations(
        graph, source,
        FindAttestationsInput(claim_or_conjecture_id=claim_id, query="明月"),
        authored_by=AGENT,
    )
    assert len(passage_ids) == 1
    passage = graph.get_node(passage_ids[0])
    assert passage.status == NodeStatus.ATTESTED  # mechanically attested by the tool
    assert graph.edges(edge_type=EdgeType.ATTESTS, src=passage_ids[0], dst=claim_id)

    # the claim is now attestable, because it has an attested-passage backer
    graph.attest(claim_id, authored_by=AGENT)
    assert graph.get_node(claim_id).status == NodeStatus.ATTESTED


def test_find_attestations_converges_witnesses_across_two_calls(graph, source):
    claim_a = graph.propose_claim(ClaimPayload(text="claim A"), authored_by=AGENT)
    claim_b = graph.propose_claim(ClaimPayload(text="claim B"), authored_by=AGENT)
    find_attestations(
        graph, source,
        FindAttestationsInput(claim_or_conjecture_id=claim_a, query="空山"),
        authored_by=AGENT,
    )
    find_attestations(
        graph, source,
        FindAttestationsInput(claim_or_conjecture_id=claim_b, query="空山"),
        authored_by=AGENT,
    )
    # both calls should have converged on the same witness node, not duplicated it
    w = graph.get_node("witness:poem:wangwei-luchai")
    assert len(w.authorship) == 2


def test_find_attestations_refuses_a_witness_target(graph, source):
    witness_id = graph.propose_witness(
        WitnessPayload(
            canonical_ref="T01n0001",
            dating=Dating(confidence=DatingRoute.UNKNOWN, basis="not dated for this test"),
        ),
        authored_by=AGENT,
    )
    with pytest.raises(ValueError, match="not a claim or conjecture"):
        find_attestations(
            graph, source,
            FindAttestationsInput(claim_or_conjecture_id=witness_id, query="明月"),
            authored_by=AGENT,
        )


def test_find_attestations_carries_restrictive_license_terms_onto_the_witness(graph, tmp_path):
    import hashlib
    import zipfile
    from io import BytesIO

    entry_path = "Bookcase/CBETA/XML/T/T02/T02n0099_001.xml"
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<TEI><teiHeader><fileDesc>synthetic fixture</fileDesc></teiHeader>"
        "<text>諸行無常。是生滅法。</text></TEI>\n"
    ).encode("utf-8")
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(entry_path, document)
    archive_bytes = buf.getvalue()
    path = tmp_path / "synthetic-cbeta.zip"
    path.write_bytes(archive_bytes)
    digest = hashlib.sha256(archive_bytes).hexdigest()

    cbeta_source = CbetaReader(path, digest, index={entry_path: ["諸行無常"]})
    claim_id = graph.propose_claim(ClaimPayload(text="a claim about impermanence"), authored_by=AGENT)
    find_attestations(
        graph, cbeta_source,
        FindAttestationsInput(claim_or_conjecture_id=claim_id, query="諸行無常"),
        authored_by=AGENT,
    )
    witness = graph.get_node("witness:T02n0099")
    assert "CC BY-NC-SA-equivalent" in witness.payload["source_terms"]
    assert entry_path in witness.payload["source_terms"]


def _conjecture_input(**overrides):
    defaults = dict(
        text="An earlier Kuchean recension underlies this passage",
        derivation="vocabulary matches Kuchean loanword patterns",
        corpus_boundary="only the local_corpus fixture was searched",
        selection_risks="none identified",
        alternative_explanations="a later redactor independently chose similar vocabulary",
        prior_art_query="Kuchean recension",
        tests_query_text="search Kuchean fragment catalogues for a parallel",
    )
    defaults.update(overrides)
    return ProposeConjectureInput(**defaults)


def test_propose_conjecture_creates_conjecture_query_and_tests_edge(graph, source):
    conjecture_id = propose_conjecture(graph, source, _conjecture_input(), authored_by=AGENT)
    node = graph.get_node(conjecture_id)
    assert node.type == "conjecture"
    assert len(graph.edges(edge_type=EdgeType.TESTS, dst=conjecture_id)) == 1


def test_propose_conjecture_records_the_prior_art_search_as_run(graph, source):
    conjecture_id = propose_conjecture(graph, source, _conjecture_input(), authored_by=AGENT)
    searched_for = graph.edges(edge_type=EdgeType.SEARCHED_FOR, dst=conjecture_id)
    assert len(searched_for) == 1
    query_node = graph.get_node(searched_for[0].src)
    assert query_node.type == "query"
    assert "Kuchean recension" in query_node.payload["text"]


def test_conjecture_without_the_tool_stays_unattestable(graph):
    conjecture_id = graph.propose_conjecture(
        ConjecturePayload(
            text="bare conjecture",
            derivation="none",
            corpus_boundary="none",
            selection_risks="none identified",
            alternative_explanations="none identified",
        ),
        authored_by=AGENT,
    )
    with pytest.raises(UnattestableConjecture):
        graph.attest(conjecture_id, authored_by=AGENT)


def test_propose_conjecture_result_is_attestable(graph, source):
    conjecture_id = propose_conjecture(
        graph, source, _conjecture_input(text="claim", tests_query_text="a testing query"),
        authored_by=AGENT,
    )
    graph.attest(conjecture_id, authored_by=AGENT)
    assert graph.get_node(conjecture_id).status == NodeStatus.ATTESTED


# --- propose_claim ------------------------------------------------------------

def test_propose_claim_creates_a_claim_and_records_the_grounding_search(graph, source):
    claim_id = propose_claim(
        graph, source,
        ProposeClaimInput(
            text="The moon figures as homesickness in this corpus",
            grounding_query="明月",
        ),
        authored_by=AGENT,
    )
    node = graph.get_node(claim_id)
    assert node.type == "claim"
    assert node.status == NodeStatus.PROPOSED

    searched_for = graph.edges(edge_type=EdgeType.SEARCHED_FOR, dst=claim_id)
    assert len(searched_for) == 1
    query_node = graph.get_node(searched_for[0].src)
    assert query_node.type == "query"
    assert "明月" in query_node.payload["text"]


def test_propose_claim_refuses_an_ungrounded_claim_and_writes_nothing(graph, source):
    before = len(graph.nodes())
    with pytest.raises(ValueError, match="no hits"):
        propose_claim(
            graph, source,
            ProposeClaimInput(text="ungrounded", grounding_query="龍樹菩薩勸誡王頌"),
            authored_by=AGENT,
        )
    # the refusal path leaves no orphan claim and no orphan query node
    assert len(graph.nodes()) == before


def test_propose_claim_points_an_absence_at_propose_conjecture(graph, source):
    """The one legitimate case the grounding guard turns away should say where
    it belongs, rather than leaving the agent to guess."""
    with pytest.raises(ValueError, match="conjecture"):
        propose_claim(
            graph, source,
            ProposeClaimInput(
                text="This phrase never occurs in the corpus",
                grounding_query="龍樹菩薩勸誡王頌",
            ),
            authored_by=AGENT,
        )


def test_propose_claim_result_is_not_attestable_until_it_cites_something(graph, source):
    """A grounded claim is still only `proposed`: the grounding search
    establishes that something is citable, not that it has been cited. The
    ladder's own rule (design doc §8) is what makes the claim wait for real
    attests edges, and propose_claim must not shortcut it."""
    claim_id = propose_claim(
        graph, source,
        ProposeClaimInput(text="a grounded claim", grounding_query="明月"),
        authored_by=AGENT,
    )
    with pytest.raises(UnattestableClaim):
        graph.attest(claim_id, authored_by=AGENT)

    find_attestations(
        graph, source,
        FindAttestationsInput(claim_or_conjecture_id=claim_id, query="明月"),
        authored_by=AGENT,
    )
    graph.attest(claim_id, authored_by=AGENT)
    assert graph.get_node(claim_id).status == NodeStatus.ATTESTED


def test_searched_for_still_refuses_a_query_pointing_at_a_passage(graph, source):
    """Widening the searched_for domain to claims must not have opened it to
    everything (design doc: the vocabulary stays closed)."""
    from cohort.errors import EdgeDomainViolation

    claim_id = propose_claim(
        graph, source,
        ProposeClaimInput(text="a claim", grounding_query="明月"),
        authored_by=AGENT,
    )
    passage_ids = find_attestations(
        graph, source,
        FindAttestationsInput(claim_or_conjecture_id=claim_id, query="明月"),
        authored_by=AGENT,
    )
    query_id = graph.edges(edge_type=EdgeType.SEARCHED_FOR, dst=claim_id)[0].src
    with pytest.raises(EdgeDomainViolation):
        graph.add_edge(
            EdgeType.SEARCHED_FOR, query_id, passage_ids[0], authored_by=AGENT,
        )
