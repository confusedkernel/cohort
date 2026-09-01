"""AttestationWorker's tool-dispatch loop, exercised against a fake
OpenRouter transport — no network, no API key. This does not prove the real
OpenRouter API round-trips correctly (see scripts/smoke_openrouter.py for
that, run once by hand); it proves the loop's own logic — message building,
tool dispatch, and error reporting — is correct.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cohort.agents.attestation_worker import AttestationWorker
from cohort.eventlog import summarize_model_calls
from cohort.schemas import RESEARCHER, AgentKind, AgentProfile, ConjecturePayload, EdgeType
from cohort.sources.local_reader import LocalReader

AGENT = "agent:worker-1"
FIXTURE = Path(__file__).parent.parent / "examples" / "local_corpus"


@pytest.fixture
def source():
    r = LocalReader(FIXTURE)
    yield r
    r.close()


def _tool_call(name, args, id_="call_1"):
    return {"id": id_, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _response(*, content=None, tool_calls=None, finish_reason, input_tokens=10,
              output_tokens=5, cost=None, model="test-model"):
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "gen-1", "model": model,
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens, "cost": cost},
    }


class FakeTransport:
    """The test seam `complete()` exposes — no HTTP-mocking dependency
    needed, just a plain callable matching `(url, headers, body, timeout)
    -> (status, raw_bytes)`."""

    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(json.loads(body))
        return 200, json.dumps(self._responses.pop(0)).encode("utf-8")


def _worker(graph, *, source=None, authored_by=AGENT, transport, profile=None):
    return AttestationWorker(
        graph, source=source, authored_by=authored_by, model="test-model",
        api_key="test-key", transport=transport, profile=profile,
    )


def test_worker_runs_a_tool_call_and_then_stops(graph, source):
    transport = FakeTransport([
        _response(tool_calls=[_tool_call("propose_conjecture", {
            "text": "a conjecture",
            "derivation": "vocabulary matches a known pattern",
            "corpus_boundary": "only the local_corpus fixture was searched",
            "selection_risks": "none identified",
            "alternative_explanations": "none identified",
            "prior_art_query": "a conjecture",
            "tests_query_text": "a testing query",
        })], finish_reason="tool_calls"),
        _response(content="done", finish_reason="stop"),
    ])
    worker = _worker(graph, source=source, transport=transport)

    log = worker.run("propose a conjecture")

    assert len(log) == 1
    assert log[0]["tool"] == "propose_conjecture"
    assert log[0]["is_error"] is False
    conjecture_id = log[0]["result"]
    assert graph.get_node(conjecture_id).type == "conjecture"
    assert graph.edges(edge_type=EdgeType.TESTS, dst=conjecture_id)
    assert len(transport.calls) == 2  # one tool_calls turn, one final turn


def test_worker_logs_a_model_call_event_with_token_and_latency_metadata(graph):
    transport = FakeTransport([
        _response(content="done", finish_reason="stop", input_tokens=42, output_tokens=7, cost=0.0034),
    ])
    worker = _worker(graph, transport=transport)

    worker.run("do nothing")

    summary = summarize_model_calls(graph.event_log.path)
    assert summary.calls == 1
    assert summary.total_input_tokens == 42
    assert summary.total_output_tokens == 7
    assert summary.total_cost_usd == pytest.approx(0.0034)


def test_worker_reports_a_refused_write_as_a_tool_error_without_crashing(graph):
    transport = FakeTransport([
        _response(tool_calls=[_tool_call(
            "find_attestations", {"claim_or_conjecture_id": "claim:missing", "query": "x"},
        )], finish_reason="tool_calls"),
        _response(content="adjusting", finish_reason="stop"),
    ])
    worker = _worker(graph, transport=transport)

    log = worker.run("find attestations for a claim that doesn't exist")

    assert log[0]["is_error"] is True
    assert "NodeNotFound" in log[0]["result"]


def test_worker_prepends_rejected_conjectures_to_its_instructions(graph):
    conjecture_id = graph.propose_conjecture(
        ConjecturePayload(
            text="an earlier Kuchean recension underlies this",
            derivation="vocabulary matches Kuchean loanword patterns",
            corpus_boundary="only the local_corpus fixture was searched",
            selection_risks="none identified",
            alternative_explanations="none identified",
        ),
        authored_by=AGENT,
    )
    graph.reject(
        conjecture_id, authored_by=RESEARCHER,
        reason="no Kuchean fragment catalogue exists for this text",
    )

    transport = FakeTransport([_response(content="noted", finish_reason="stop")])
    worker = _worker(graph, transport=transport)

    worker.run("propose any conjectures worth testing")

    sent_content = transport.calls[0]["messages"][1]["content"]  # [0] is the system message
    assert "Kuchean recension" in sent_content
    assert "no Kuchean fragment catalogue exists" in sent_content
    assert "propose any conjectures worth testing" in sent_content


def test_worker_prepends_its_declared_profile(graph):
    profile = AgentProfile(
        id=AGENT, kind=AgentKind.WORKER, corpus_scope="T01-T02", method_label="philological",
    )
    transport = FakeTransport([_response(content="noted", finish_reason="stop")])
    worker = _worker(graph, transport=transport, profile=profile)

    worker.run("do something")

    sent_content = transport.calls[0]["messages"][1]["content"]
    assert "T01-T02" in sent_content
    assert "philological" in sent_content
    assert "do something" in sent_content


def test_worker_without_a_profile_sends_plain_instructions(graph):
    transport = FakeTransport([_response(content="noted", finish_reason="stop")])
    worker = _worker(graph, transport=transport)

    worker.run("do something")

    sent_content = transport.calls[0]["messages"][1]["content"]
    assert sent_content == "do something"


def test_worker_omits_rejection_context_when_nothing_is_rejected(graph):
    transport = FakeTransport([_response(content="noted", finish_reason="stop")])
    worker = _worker(graph, transport=transport)

    worker.run("propose any conjectures worth testing")

    sent_content = transport.calls[0]["messages"][1]["content"]
    assert sent_content == "propose any conjectures worth testing"


def test_worker_stops_immediately_on_end_turn_with_no_tool_use(graph):
    transport = FakeTransport([_response(content="nothing to do", finish_reason="stop")])
    worker = _worker(graph, transport=transport)

    log = worker.run("do nothing")

    assert log == []
    assert len(transport.calls) == 1
