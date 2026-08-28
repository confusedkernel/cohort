"""AttestationWorker's tool-dispatch loop, exercised against a fake
Anthropic client — no network, no API key. This does not prove the real
`anthropic.Anthropic` client round-trips correctly (untested, see the module
docstring in attestation_worker.py); it proves the loop's own logic —
message building, tool dispatch, and error reporting — is correct.
"""
from __future__ import annotations

from types import SimpleNamespace

from meep.agents.attestation_worker import AttestationWorker
from meep.schemas import EdgeType

AGENT = "agent:worker-1"


def _tool_use_block(name, input_, id_):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=id_)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def test_worker_runs_a_tool_call_and_then_stops(graph):
    responses = [
        SimpleNamespace(
            content=[_tool_use_block(
                "propose_conjecture",
                {"text": "a conjecture", "tests_query_text": "a testing query"},
                "call_1",
            )],
            stop_reason="tool_use",
        ),
        SimpleNamespace(content=[_text_block("done")], stop_reason="end_turn"),
    ]
    client = FakeClient(responses)
    worker = AttestationWorker(graph, source=None, authored_by=AGENT, client=client)

    log = worker.run("propose a conjecture")

    assert len(log) == 1
    assert log[0]["tool"] == "propose_conjecture"
    assert log[0]["is_error"] is False
    conjecture_id = log[0]["result"]
    assert graph.get_node(conjecture_id).type == "conjecture"
    assert graph.edges(edge_type=EdgeType.TESTS, dst=conjecture_id)
    assert len(client.messages.calls) == 2  # one tool_use turn, one final turn


def test_worker_reports_a_refused_write_as_a_tool_error_without_crashing(graph):
    responses = [
        SimpleNamespace(
            content=[_tool_use_block(
                "find_attestations",
                {"claim_or_conjecture_id": "claim:missing", "query": "x"},
                "call_1",
            )],
            stop_reason="tool_use",
        ),
        SimpleNamespace(content=[_text_block("adjusting")], stop_reason="end_turn"),
    ]
    client = FakeClient(responses)
    worker = AttestationWorker(graph, source=None, authored_by=AGENT, client=client)

    log = worker.run("find attestations for a claim that doesn't exist")

    assert log[0]["is_error"] is True
    assert "NodeNotFound" in log[0]["result"]


def test_worker_stops_immediately_on_end_turn_with_no_tool_use(graph):
    responses = [SimpleNamespace(content=[_text_block("nothing to do")], stop_reason="end_turn")]
    client = FakeClient(responses)
    worker = AttestationWorker(graph, source=None, authored_by=AGENT, client=client)

    log = worker.run("do nothing")

    assert log == []
    assert len(client.messages.calls) == 1
