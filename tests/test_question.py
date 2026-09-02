"""Research questions — what an inquiry was asking.

A new node type, so §6 requires an argument and these tests pin the shape that
argument commits to. The interesting properties are the negative ones: a
question is not evidence, is not runnable, is not a container, and cannot be
asked by an agent.
"""
from __future__ import annotations

import pytest

from cohort.errors import EdgeDomainViolation, NotResearcher
from cohort.eventlog import EventLog, read_events
from cohort.graph import Graph
from cohort.schemas import (
    RESEARCHER,
    ClaimPayload,
    ConjecturePayload,
    EdgeType,
    NodeStatus,
    NodeType,
    QueryPayload,
    QuestionPayload,
)
from cohort.views import question_json, questions_json

AGENT = "agent:worker-1"

QUESTION = QuestionPayload(
    text="Which witnesses share a transcription of the closing dhāraṇī?",
    answerable_by="retrieval over the corpus as indexed; it cannot settle which is earlier",
)


def ask(graph) -> str:
    return graph.ask_question(QUESTION, authored_by=RESEARCHER)


# --- who may ask -------------------------------------------------------------

def test_only_the_researcher_asks(graph):
    """Setting the agenda is the supervision. An agent that could ask its own
    question and then answer it would be doing unsupervised research with a
    paper trail — the same reasoning that makes accept/reject researcher-only."""
    with pytest.raises(NotResearcher, match="sets the agenda"):
        graph.ask_question(QUESTION, authored_by=AGENT)


def test_the_refusal_reaches_the_log(graph):
    with pytest.raises(NotResearcher):
        graph.ask_question(QUESTION, authored_by=AGENT)
    refused = [e for e in read_events(graph.event_log.path) if e.event == "refused"]
    assert refused and refused[-1].detail["rule"] == "NotResearcher"
    assert refused[-1].detail["attempted"] == "ask"


# --- what it is, and is not --------------------------------------------------

def test_a_question_is_asked_not_proposed(graph):
    """It does not climb the ladder — there is no mechanical check that could
    promote a question — so it gets its own event rather than sharing
    `propose`, which is what puts a node on the bottom rung."""
    qid = ask(graph)
    assert graph.get_node(qid).status == NodeStatus.ACCEPTED
    events = [e for e in read_events(graph.event_log.path) if e.node_id == qid]
    assert [e.event for e in events] == ["ask"]


def test_accepted_means_asked_not_answered(graph):
    """`citable()` returns accepted nodes, so without the exclusion a question
    would become quotable as a premise the moment it was written down. Output
    cites what answers a question, never the question."""
    qid = ask(graph)
    assert qid not in [n.id for n in graph.citable()]


def test_a_question_is_not_a_query(graph):
    """A query is a retrieval to run; a question is not runnable. Conflating
    them would put a research question where `tests` and `searched_for` expect
    something executable."""
    qid = ask(graph)
    query_id = graph.propose_query(QueryPayload(text="揭諦揭諦"), authored_by=AGENT)
    assert graph.get_node(qid).type == NodeType.QUESTION
    assert graph.get_node(query_id).type == NodeType.QUERY
    conjecture_id = graph.propose_conjecture(
        ConjecturePayload(text="c", derivation="d", corpus_boundary="b",
                          selection_risks="s", alternative_explanations="a"),
        authored_by=AGENT,
    )
    with pytest.raises(EdgeDomainViolation):
        graph.add_edge(EdgeType.TESTS, qid, conjecture_id, authored_by=AGENT)


def test_only_claims_and_conjectures_may_address_one(graph):
    qid = ask(graph)
    claim_id = graph.propose_claim(ClaimPayload(text="a claim"), authored_by=AGENT)
    graph.add_edge(EdgeType.ADDRESSES, claim_id, qid, authored_by=AGENT)

    query_id = graph.propose_query(QueryPayload(text="q"), authored_by=AGENT)
    with pytest.raises(EdgeDomainViolation):
        graph.add_edge(EdgeType.ADDRESSES, query_id, qid, authored_by=AGENT)


def test_the_edge_points_from_the_answer_to_the_question(graph):
    """Not the other way round. A question pointing at its answers would make
    it a container, and a container with nine claims in it reads as a question
    that has been answered — a conclusion no edge should draw."""
    qid = ask(graph)
    claim_id = graph.propose_claim(ClaimPayload(text="a claim"), authored_by=AGENT)
    with pytest.raises(EdgeDomainViolation):
        graph.add_edge(EdgeType.ADDRESSES, qid, claim_id, authored_by=AGENT)


# --- reading it back ---------------------------------------------------------

def test_the_view_tallies_and_does_not_conclude(graph):
    qid = ask(graph)
    for i in range(3):
        c = graph.propose_claim(ClaimPayload(text=f"claim {i}"), authored_by=AGENT)
        graph.add_edge(EdgeType.ADDRESSES, c, qid, authored_by=AGENT)

    view = question_json(graph, qid)
    assert view["question"] == QUESTION.text
    assert view["answerable_by"] == QUESTION.answerable_by
    assert len(view["hypotheses"]) == 3
    assert view["by_status"] == {"proposed": 3}
    # nothing attests any of them, and the view says so rather than reporting
    # three independently-supported answers
    assert view["unsupported"] == 3
    assert "answered" not in str(view)


def test_questions_list_counts_what_addresses_each(graph):
    first = ask(graph)
    second = graph.ask_question(
        QuestionPayload(text="another", answerable_by="retrieval"), authored_by=RESEARCHER,
    )
    c = graph.propose_claim(ClaimPayload(text="a claim"), authored_by=AGENT)
    graph.add_edge(EdgeType.ADDRESSES, c, first, authored_by=AGENT)

    listing = questions_json(graph)
    assert listing["count"] == 2
    assert [q["id"] for q in listing["questions"]] == [second, first], "newest first"
    assert {q["id"]: q["addressed_by"] for q in listing["questions"]} == {first: 1, second: 0}


def test_a_question_needs_to_say_what_would_answer_it(graph):
    """A question nobody can say how to answer is not a research question, it
    is a mood. Enforced by pydantic at the boundary, like the conjecture
    dossier."""
    with pytest.raises(Exception, match="answerable_by"):
        QuestionPayload(text="what happened?")


# --- it replays --------------------------------------------------------------

def test_rebuild_matches_live_with_questions_present(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    g = Graph(tmp_path / "graph.sqlite", event_log=log)
    qid = g.ask_question(QUESTION, authored_by=RESEARCHER)
    c = g.propose_claim(ClaimPayload(text="a claim"), authored_by=AGENT)
    g.add_edge(EdgeType.ADDRESSES, c, qid, authored_by=AGENT)
    assert g.rebuild().ok is True
    g.close()
