"""Append-only JSONL log semantics (design doc §5 principle 1, §11)."""
from __future__ import annotations

from meep.eventlog import EventLog, read_events, summarize_model_calls


def test_append_is_flushed_and_readable_immediately(tmp_path):
    log_path = tmp_path / "events.jsonl"
    log = EventLog(log_path)
    log.append(
        "propose", authored_by="agent:worker-1", node_id="witness:A",
        node_type="witness", detail={},
    )
    events = list(read_events(log_path))
    assert len(events) == 1
    assert events[0].seq == 0
    assert events[0].node_id == "witness:A"


def test_seq_is_monotonic(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    a = log.append("propose", authored_by="a", node_id="x", node_type="claim", detail={})
    b = log.append("propose", authored_by="a", node_id="y", node_type="claim", detail={})
    assert b.seq == a.seq + 1


def test_constructor_does_not_truncate_an_existing_log(tmp_path):
    path = tmp_path / "events.jsonl"
    log1 = EventLog(path)
    log1.append("propose", authored_by="a", node_id="x", node_type="claim", detail={})

    log2 = EventLog(path)  # reopen — must not wipe the file
    assert len(list(read_events(path))) == 1
    log2.append("propose", authored_by="a", node_id="y", node_type="claim", detail={})
    assert len(list(read_events(path))) == 2


def test_new_log_picks_up_seq_after_existing_events(tmp_path):
    path = tmp_path / "events.jsonl"
    EventLog(path).append("propose", authored_by="a", node_id="x", node_type="claim", detail={})
    log2 = EventLog(path)
    c = log2.append("propose", authored_by="a", node_id="y", node_type="claim", detail={})
    assert c.seq == 1


def test_read_events_never_creates_the_file(tmp_path):
    path = tmp_path / "missing.jsonl"
    assert list(read_events(path)) == []
    assert not path.exists()


def test_read_events_ignores_blank_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.append("propose", authored_by="a", node_id="x", node_type="claim", detail={})
    with path.open("a") as f:
        f.write("\n")
    assert len(list(read_events(path))) == 1


def test_summarize_model_calls_sums_only_model_call_events(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.append("propose", authored_by="a", node_id="x", node_type="claim", detail={})
    log.append(
        "model_call", authored_by="a", model="claude-test",
        latency_ms=100, input_tokens=10, output_tokens=4, cost_usd=0.02,
    )
    log.append(
        "model_call", authored_by="a", model="claude-test",
        latency_ms=50, input_tokens=6, output_tokens=2, cost_usd=0.01,
    )
    summary = summarize_model_calls(path)
    assert summary.calls == 2
    assert summary.total_input_tokens == 16
    assert summary.total_output_tokens == 6
    assert summary.total_latency_ms == 150
    assert summary.total_cost_usd == 0.03


def test_summarize_model_calls_on_empty_log(tmp_path):
    summary = summarize_model_calls(tmp_path / "missing.jsonl")
    assert summary.calls == 0
    assert summary.total_cost_usd == 0.0
