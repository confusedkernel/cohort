"""The terminal front end.

The parity *structure* is checked in `tests/test_parity.py`; this checks the
commands actually work, and that the two front ends give the same answers —
parity is only worth anything if `cohort node X` and `GET /api/node?id=X` agree
about X.
"""
from __future__ import annotations

import json

import pytest

from cohort.cli import main
from cohort.graph import Graph
from cohort.schemas import (
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

AGENT = "agent:worker-1"


@pytest.fixture
def seeded(tmp_path):
    """The Heart Sutra shape: one claim, two witnesses the corpus calls
    parallel, so `independent` is genuinely False rather than trivially True."""
    db, log = tmp_path / "graph.sqlite", tmp_path / "graph.jsonl"
    g = Graph.open(db, log)
    g.register_agent(
        AgentProfile(id=AGENT, kind=AgentKind.WORKER, corpus_scope="CBETA",
                     method_label="textual"),
        authored_by=AGENT,
    )
    claim = g.propose_claim(ClaimPayload(text="form is emptiness"), authored_by=AGENT)
    witnesses = []
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
        g.add_edge(EdgeType.ATTESTS, p, claim, authored_by=AGENT)
        witnesses.append(w)
    g.add_edge(EdgeType.PARALLEL_OF, witnesses[0], witnesses[1], authored_by=AGENT)
    g.attest(claim, authored_by=AGENT)
    g.close()
    return {"db": str(db), "log": str(log), "claim": claim}


def run(seeded, *argv, capsys) -> str:
    main(["--db", seeded["db"], *argv])
    return capsys.readouterr().out


def run_json(seeded, *argv, capsys):
    return json.loads(run(seeded, "--json", *argv, capsys=capsys))


# --- reads ------------------------------------------------------------------

def test_health_counts_nodes(seeded, capsys):
    out = run_json(seeded, "health", capsys=capsys)
    assert out["nodes"]["claim"] == 1
    assert out["nodes"]["witness"] == 2


def test_node_reports_support_as_not_independent(seeded, capsys):
    """The system's central output, in the terminal: agreement between two
    witnesses the corpus calls parallel is one transmission event, not two
    confirmations."""
    out = run_json(seeded, "node", seeded["claim"], capsys=capsys)
    sup = out["independent_support"]
    assert sup["attesting_count"] == 2
    assert sup["independent"] is False
    assert sup["non_independent_pairs"]


def test_node_human_output_states_the_discount(seeded, capsys):
    """A reader must not have to infer it from a count that looks healthy."""
    out = run(seeded, "node", seeded["claim"], capsys=capsys)
    assert "NOT independent" in out


def test_citable_is_empty_until_the_researcher_accepts(seeded, capsys):
    assert run_json(seeded, "citable", capsys=capsys) == []


def test_rebuild_matches_the_projection(seeded, capsys):
    out = run_json(seeded, "rebuild", capsys=capsys)
    assert out["ok"] is True and out["events_replayed"] > 0


def test_integrity_finds_no_tampering(seeded, capsys):
    out = run_json(seeded, "integrity", capsys=capsys)
    assert out["mismatched"] == [] and out["checked"] > 0


def test_rebuild_without_a_log_says_so_rather_than_claiming_ok(tmp_path, capsys):
    """A missing log must not read as a passing check."""
    db = tmp_path / "g.sqlite"
    Graph.open(db, tmp_path / "g.jsonl").close()
    (tmp_path / "g.jsonl").unlink()
    main(["--db", str(db), "--json", "rebuild"])
    out = json.loads(capsys.readouterr().out)
    assert out["available"] is False and "ok" not in out


# --- writes -----------------------------------------------------------------

def test_accept_promotes_and_makes_citable(seeded, capsys):
    run(seeded, "accept", seeded["claim"], capsys=capsys)
    assert run_json(seeded, "node", seeded["claim"], capsys=capsys)["status"] == "accepted"
    assert len(run_json(seeded, "citable", capsys=capsys)) == 1


def test_reject_records_the_reason(seeded, capsys):
    run(seeded, "reject", seeded["claim"], "--reason", "conflates two recensions", capsys=capsys)
    rejected = run_json(seeded, "rejected", capsys=capsys)
    assert rejected[0]["rejected_reason"] == "conflates two recensions"


def test_a_refused_write_exits_nonzero_and_is_logged(seeded, capsys):
    """Skipping a rung is refused identically here and over HTTP, because both
    call `Graph.accept()` — the rule lives at the write boundary, not in either
    front end."""
    g = Graph.open(seeded["db"], seeded["log"])
    fresh = g.propose_claim(ClaimPayload(text="ungrounded"), authored_by=AGENT)
    g.close()
    with pytest.raises(SystemExit) as e:
        main(["--db", seeded["db"], "accept", fresh])
    assert e.value.code == 2
    assert "refused" in capsys.readouterr().err

    out = run_json(seeded, "refusals", capsys=capsys)
    assert out["available"] and out["total"] >= 1


def test_reject_requires_a_reason_at_the_parser(seeded):
    with pytest.raises(SystemExit):
        main(["--db", seeded["db"], "reject", seeded["claim"]])


def test_writes_refuse_while_another_writer_holds_the_lock(seeded):
    """Same answer the API gives as a 409."""
    holder = Graph.open(seeded["db"], seeded["log"])
    try:
        with pytest.raises(SystemExit) as e:
            main(["--db", seeded["db"], "accept", seeded["claim"]])
        assert "locked" in str(e.value)
    finally:
        holder.close()


def test_missing_graph_is_a_clear_message_not_a_traceback(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["--db", str(tmp_path / "nope.sqlite"), "health"])
    assert "no graph at" in str(e.value)


# --- the two front ends agree ----------------------------------------------

def test_cli_and_http_return_the_same_node(seeded, capsys):
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    from cohort.ui.api import create_app

    from_cli = run_json(seeded, "node", seeded["claim"], capsys=capsys)
    client = TestClient(create_app(seeded["db"], seeded["log"]))
    from_http = client.get("/api/node", params={"id": seeded["claim"]}).json()

    # Whole-payload equality, not a spot check: both call `node_detail_json`,
    # so any field one grows and the other doesn't should fail here. An earlier
    # version of this test compared three keys and missed that the two front
    # ends disagreed about the shape entirely.
    assert from_cli == from_http


# --- `run`, without spending anything ---------------------------------------

def test_run_builds_one_spec_per_agent_and_passes_the_budget(seeded, monkeypatch, capsys):
    """`cohort run` is the one command that cannot be exercised against a live
    model in a test, so its wiring is checked directly: the flags a user types
    must reach `RunManager` unchanged, especially the budget."""
    import cohort.ui.runs as runs_mod

    seen = {}

    class FakeManager:
        def __init__(self, db, log, source, *, max_budget_usd, max_turns, **kw):
            seen["ceiling"] = max_budget_usd
            seen["max_turns"] = max_turns

        def start(self, specs, *, budget_usd, max_turns=None):
            seen["specs"] = specs
            seen["budget"] = budget_usd

        def current(self):
            return None

        def history(self, limit=10):
            return [{
                "state": "finished", "elapsed_s": 1,
                "spend": {"spent_usd": 0.001, "budget_usd": seen["budget"], "calls": 2},
                "agents": [{"agent_id": "agent:cli-1", "tool_calls": [], "error": None}],
            }]

        def stop(self):
            pass

    monkeypatch.setattr(runs_mod, "RunManager", FakeManager)
    monkeypatch.setattr("cohort.cli._corpus", lambda args: object())

    main([
        "--db", seeded["db"], "run",
        "--agent", "find attestations for 色即是空",
        "--agent", "collate the editions",
        "--scope", "Prajñāpāramitā only", "--method", "phrase distribution",
        "--budget", "0.05",
    ])

    assert seen["budget"] == 0.05
    assert seen["ceiling"] == 0.05
    assert [s.agent_id for s in seen["specs"]] == ["agent:cli-1", "agent:cli-2"]
    # Declared scope and method are what make two agents' disagreement mean
    # something, so they must not be dropped on the way through.
    assert all(s.corpus_scope == "Prajñāpāramitā only" for s in seen["specs"])
    assert all(s.method_label == "phrase distribution" for s in seen["specs"])
    assert "finished" in capsys.readouterr().out


def test_run_reports_a_refused_start_rather_than_a_traceback(seeded, monkeypatch):
    import cohort.ui.runs as runs_mod

    class Rejecting:
        def __init__(self, *a, **kw):
            pass

        def start(self, *a, **kw):
            raise runs_mod.RunRejected("budget above the server ceiling")

    monkeypatch.setattr(runs_mod, "RunManager", Rejecting)
    monkeypatch.setattr("cohort.cli._corpus", lambda args: object())

    with pytest.raises(SystemExit) as e:
        main(["--db", seeded["db"], "run", "--agent", "x", "--budget", "99"])
    assert "refused" in str(e.value)
