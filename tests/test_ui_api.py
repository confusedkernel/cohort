"""The read-only JSON API (build order stage 5).

Two properties matter more than the routing: the API cannot write, and it
does not flatten the epistemics DESIGN.md §10 warns about — status travels
with every node, and edges that *discount* support are marked as such rather
than looking like edges that add it.
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="the `ui` extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from cohort.graph import Graph  # noqa: E402
from cohort.schemas import (  # noqa: E402
    RESEARCHER,
    AgentKind,
    AgentProfile,
    ClaimPayload,
    Dating,
    DatingRoute,
    EdgeType,
    PassagePayload,
    WitnessPayload,
)
from cohort.ui.api import create_app  # noqa: E402

AGENT = "agent:worker-1"


@pytest.fixture
def populated(tmp_path):
    """A graph shaped like the real Heart Sutra case: one claim supported by
    two witnesses that the corpus says are parallel, so the discounting edge
    is present and independence is genuinely False."""
    db_path = tmp_path / "graph.sqlite"
    g = Graph.open(db_path, tmp_path / "events.jsonl")
    g.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="CBETA", method_label="textual"),
        authored_by=AGENT,
    )
    claim_id = g.propose_claim(ClaimPayload(text="form is emptiness"), authored_by=AGENT)
    passages = []
    for ref in ("T08n0251", "T08n0252"):
        w = g.propose_witness(
            WitnessPayload(
                canonical_ref=ref,
                dating=Dating(confidence=DatingRoute.UNKNOWN, basis="not dated for this test"),
            ),
            authored_by=AGENT,
        )
        p = g.propose_passage(
            PassagePayload(canonical_ref=f"{ref}#x", locator="juan 1", excerpt="色即是空"),
            witness_id=w, authored_by=AGENT,
        )
        g.attest(p, authored_by=AGENT)
        g.add_edge(EdgeType.ATTESTS, p, claim_id, authored_by=AGENT)
        passages.append((w, p))
    g.add_edge(EdgeType.PARALLEL_OF, passages[0][0], passages[1][0], authored_by=AGENT)
    g.attest(claim_id, authored_by=AGENT)
    g.accept(claim_id, authored_by=RESEARCHER)
    g.close()
    return db_path, claim_id


@pytest.fixture
def client(populated):
    db_path, _ = populated
    return TestClient(create_app(db_path))


def test_health_reports_counts(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["nodes"]["claim"] == 1
    assert body["nodes"]["witness"] == 2


def test_graph_view_carries_status_on_every_node(client):
    """§10: 'node status is a visual channel, not a tooltip'. The frontend
    cannot render what the API does not send."""
    body = client.get("/api/graph").json()
    assert body["nodes"]
    assert all("status" in n for n in body["nodes"])
    assert all("assurance" in n for n in body["nodes"])


def test_discounting_edges_are_marked_as_such(client):
    """§4: parallel_of/descends_from reduce support rather than adding it.
    An edge list that did not say so would let a densely-linked node look
    well-supported regardless of independence."""
    body = client.get("/api/graph").json()
    by_type = {e["type"]: e for e in body["edges"]}
    assert by_type["parallel_of"]["discounts"] is True
    assert by_type["attests"]["discounts"] is False
    assert set(body["discounting_edge_types"]) == {"descends_from", "parallel_of"}


def test_graph_view_reports_truncation_explicitly(client):
    body = client.get("/api/graph", params={"limit": 2}).json()
    assert len(body["nodes"]) == 2
    assert body["truncated"] is True


def test_node_detail_carries_provenance_and_independence(client, populated):
    _, claim_id = populated
    body = client.get("/api/node", params={"id": claim_id}).json()
    assert body["payload"]["text"] == "form is emptiness"
    assert body["authorship"]
    assert body["edges_in"]
    support = body["independent_support"]
    assert support["attesting_count"] == 2
    assert support["independent"] is False  # the two witnesses are parallel
    assert support["non_independent_pairs"]


def test_witness_detail_has_no_independence_block(client):
    body = client.get("/api/node", params={"id": "witness:T08n0251"}).json()
    assert "independent_support" not in body


def test_node_id_containing_a_hash_is_reachable(client):
    """Passage ids are `{witness}#{excerpt}`. In a path segment the `#` would
    start a URL fragment and never reach the server, so the id travels as a
    query parameter."""
    body = client.get("/api/node", params={"id": "passage:T08n0251#x"}).json()
    assert body["id"] == "passage:T08n0251#x"
    assert body["payload"]["excerpt"] == "色即是空"


def test_missing_node_is_404(client):
    assert client.get("/api/node", params={"id": "claim:nope"}).status_code == 404


def test_citable_lists_only_accepted_evidence(client, populated):
    _, claim_id = populated
    ids = [n["id"] for n in client.get("/api/citable").json()]
    assert claim_id in ids


def test_agent_report_includes_declared_scope(client):
    body = client.get("/api/agent", params={"id": AGENT}).json()
    assert body["proposed"] > 0
    assert body["profile"]["corpus_scope"] == "CBETA"


# --- the API must not be able to write --------------------------------------

def test_api_exposes_no_mutating_routes(client):
    """Accept/reject are writes and are deliberately absent: a writing UI
    would need the exclusive lock for as long as a tab is open."""
    methods = {m for r in client.app.routes for m in getattr(r, "methods", set())}
    assert methods <= {"GET", "HEAD", "OPTIONS"}


def test_api_serves_while_a_writer_holds_the_lock(populated):
    """The whole point of the read-only path: a researcher can watch the
    graph while an agent run is writing to it."""
    db_path, claim_id = populated
    writer = Graph.open(db_path, db_path.parent / "events.jsonl")
    try:
        client = TestClient(create_app(db_path))
        assert client.get("/api/node", params={"id": claim_id}).status_code == 200
    finally:
        writer.close()


def test_missing_projection_is_503_not_a_crash(tmp_path):
    client = TestClient(create_app(tmp_path / "absent.sqlite"))
    assert client.get("/api/health").status_code == 503
