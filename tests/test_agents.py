"""Agent identity: a sidecar record, not a graph node (docs/roadmap.md "Scope
revision", agent-society axis, steps 1-3 — registration and a
contribution-history report only; reputation scoring and asyncio fan-out
are explicitly deferred).
"""
from __future__ import annotations

from cohort.eventlog import EventLog
from cohort.graph import Graph
from cohort.schemas import (
    RESEARCHER,
    AgentKind,
    AgentProfile,
    ClaimPayload,
    Dating,
    DatingRoute,
    EdgeType,
    WitnessPayload,
)

AGENT = "agent:worker-1"
AGENT_2 = "agent:worker-2"


def test_register_agent_stores_declared_scope(graph):
    graph.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="T01-T02", method_label="philological"),
        authored_by=AGENT,
    )
    profile = graph.agent_profile(AGENT)
    assert profile.corpus_scope == "T01-T02"
    assert profile.method_label == "philological"
    assert profile.kind == AgentKind.WORKER


def test_agent_profile_is_none_for_unregistered_agent(graph):
    assert graph.agent_profile("agent:never-registered") is None


def test_authored_by_works_unregistered(graph):
    """Registration is informational, not enforced — an unregistered
    authored_by string still writes normally."""
    claim_id = graph.propose_claim(ClaimPayload(text="a claim"), authored_by="agent:unregistered")
    assert graph.get_node(claim_id).authorship[0].author == "agent:unregistered"


def test_re_registering_updates_rather_than_errors(graph):
    graph.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="T01-T02"), authored_by=AGENT
    )
    graph.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="T03-T05"), authored_by=AGENT
    )
    assert graph.agent_profile(AGENT).corpus_scope == "T03-T05"


def test_two_agents_can_declare_distinct_scope(graph):
    graph.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="T01-T02", method_label="philological"),
        authored_by=AGENT,
    )
    graph.register_agent(
        AgentProfile(id=AGENT_2, kind=AgentKind.WORKER, corpus_scope="T03-T05", method_label="doctrinal"),
        authored_by=AGENT_2,
    )
    assert graph.agent_profile(AGENT).corpus_scope != graph.agent_profile(AGENT_2).corpus_scope


def test_agent_report_counts_ladder_actions(graph):
    # only the researcher may reject (§8), so "rejected" shows on the
    # researcher's own report, not the proposing agent's — check both.
    c1 = graph.propose_claim(ClaimPayload(text="claim A"), authored_by=AGENT)
    graph.reject(c1, authored_by=RESEARCHER, reason="unsupported")

    w = graph.propose_witness(
        WitnessPayload(canonical_ref="T01n0001", dating=Dating(confidence=DatingRoute.SOURCE_LABEL, basis="colophon states a Northern Song printing")),
        authored_by=AGENT,
    )
    graph.attest(w, authored_by=AGENT)

    agent_report = graph.agent_report(AGENT)
    assert agent_report.proposed == 2  # the claim and the witness
    assert agent_report.attested == 1  # the witness
    assert agent_report.rejected == 0  # the agent never rejects anything

    researcher_report = graph.agent_report(RESEARCHER)
    assert researcher_report.rejected == 1


def test_agent_report_counts_discount_edges_contributed(graph):
    w1 = graph.propose_witness(
        WitnessPayload(canonical_ref="T01n0001", dating=Dating(confidence=DatingRoute.SOURCE_LABEL, basis="colophon states a Northern Song printing")),
        authored_by=AGENT,
    )
    w2 = graph.propose_witness(
        WitnessPayload(canonical_ref="T02n0002", dating=Dating(confidence=DatingRoute.SOURCE_LABEL, basis="colophon states a Northern Song printing")),
        authored_by=AGENT,
    )
    graph.add_edge(EdgeType.DESCENDS_FROM, w2, w1, authored_by=AGENT)

    report = graph.agent_report(AGENT)
    assert report.discount_edges_contributed == 1


def test_agent_report_works_for_an_unregistered_agent(graph):
    graph.propose_claim(ClaimPayload(text="a claim"), authored_by="agent:never-registered")
    report = graph.agent_report("agent:never-registered")
    assert report.proposed == 1


def test_rebuild_matches_live_with_agent_registrations_present(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    g = Graph(tmp_path / "graph.sqlite", event_log=log)
    g.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="T01-T02"), authored_by=AGENT
    )
    g.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="T03-T05"), authored_by=AGENT
    )
    report = g.rebuild()
    assert report.ok is True
    g.close()
