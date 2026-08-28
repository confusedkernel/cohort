"""MEEP stage 1 demo — no corpus, no agents, no network (design doc §11).

Shows the single most important property of the system first: a claim's
attesting count stays the same while its independence flips to False the
instant a descent relation links its two supporting witnesses. That's the
three-line counter-argument to consensus-seeking (design doc §4).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from meep.eventlog import read_events
from meep.graph import Graph
from meep.schemas import (
    RESEARCHER,
    ClaimPayload,
    ConjecturePayload,
    Dating,
    DatingRoute,
    EdgeType,
    PassagePayload,
    QueryPayload,
    WitnessPayload,
)

AGENT = "agent:demo-worker"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="meep_demo_") as tmp:
        tmp_path = Path(tmp)
        g = Graph.open(tmp_path / "graph.sqlite", tmp_path / "events.jsonl")

        print("=== MEEP stage 1 demo ===\n")

        w1 = g.propose_witness(
            WitnessPayload(
                canonical_ref="T01n0001",
                label="Taisho ed., vol. 1, no. 1",
                dating=Dating(
                    confidence=DatingRoute.SOURCE_LABEL,
                    basis="colophon states a Northern Song printing",
                ),
            ),
            authored_by=AGENT,
        )
        w2 = g.propose_witness(
            WitnessPayload(
                canonical_ref="T02n0002",
                label="Taisho ed., vol. 2, no. 2",
                dating=Dating(
                    confidence=DatingRoute.UNKNOWN,
                    basis="no colophon survives, date not assigned",
                ),
            ),
            authored_by=AGENT,
        )

        p1 = g.propose_passage(
            PassagePayload(canonical_ref="T01n0001p0001a12", locator="juan 1, line 12"),
            witness_id=w1, authored_by=AGENT,
        )
        p2 = g.propose_passage(
            PassagePayload(canonical_ref="T02n0002p0003b04", locator="juan 3, line 4"),
            witness_id=w2, authored_by=AGENT,
        )
        g.attest(p1, authored_by=AGENT)
        g.attest(p2, authored_by=AGENT)

        claim_id = g.propose_claim(
            ClaimPayload(text="This sutra was translated under the Yao Qin"),
            authored_by=AGENT,
        )
        g.add_edge(EdgeType.ATTESTS, p1, claim_id, authored_by=AGENT)
        g.add_edge(EdgeType.ATTESTS, p2, claim_id, authored_by=AGENT)
        g.attest(claim_id, authored_by=AGENT)

        support = g.independent_support(claim_id)
        print("Before any descent relation is recorded:")
        print(f"  attesting_count     = {support.attesting_count}")
        print(f"  distinct_witnesses  = {support.distinct_witnesses}")
        print(f"  independent         = {support.independent}\n")

        g.add_edge(EdgeType.DESCENDS_FROM, w2, w1, authored_by=AGENT)
        support = g.independent_support(claim_id)
        print("After recording that witness 2 descends from witness 1:")
        print(f"  attesting_count     = {support.attesting_count}   (unchanged)")
        print(f"  distinct_witnesses  = {support.distinct_witnesses}")
        print(f"  independent         = {support.independent}   <- the counter-argument to consensus-seeking\n")

        decision_id = g.accept(claim_id, authored_by=RESEARCHER)
        citable_ids = {n.id for n in g.citable()}
        print(f"Researcher accepted the claim -> decision node {decision_id}")
        print(f"citable() now includes it: {claim_id in citable_ids}\n")

        print("--- the falsifiability gate ---")
        conjecture_id = g.propose_conjecture(
            ConjecturePayload(text="An earlier Kuchean recension underlies this passage"),
            authored_by=AGENT,
        )
        try:
            g.attest(conjecture_id, authored_by=AGENT)
        except Exception as e:
            print(f"attest(conjecture) with no tests edge refused: {type(e).__name__}: {e}")
        query_id = g.propose_query(
            QueryPayload(text="search Kuchean fragment catalogues for a parallel to T01n0001p0001a12"),
            authored_by=AGENT,
        )
        g.add_edge(EdgeType.TESTS, query_id, conjecture_id, authored_by=AGENT)
        g.attest(conjecture_id, authored_by=AGENT)
        print("attest(conjecture) succeeds once a tests edge names what would refute it\n")

        print("--- persistent rejection ---")
        w3 = g.propose_witness(
            WitnessPayload(
                canonical_ref="T99n9999",
                dating=Dating(confidence=DatingRoute.UNKNOWN, basis="no catalogue entry located"),
            ),
            authored_by=AGENT,
        )
        g.reject(w3, authored_by=RESEARCHER, reason="catalogue reference does not resolve to a real text")
        try:
            g.propose_witness(
                WitnessPayload(
                    canonical_ref="T99n9999",
                    dating=Dating(confidence=DatingRoute.UNKNOWN, basis="no catalogue entry located"),
                ),
                authored_by=AGENT,
            )
        except Exception as e:
            print(f"re-proposing a rejected witness is refused: {type(e).__name__}: {e}\n")

        print("--- rebuild from the event log ---")
        report = g.rebuild()
        print(
            f"rebuild: {report.events_replayed} events replayed, {report.nodes} nodes, "
            f"{report.edges} edges, matches live projection: {report.ok}\n"
        )

        refused = [e for e in read_events(tmp_path / "events.jsonl") if e.event == "refused"]
        print("--- honest log ---")
        print(f"{len(refused)} refused write(s) recorded in the log:")
        for e in refused:
            print(f"  {e.detail['attempted']} refused: {e.detail['rule']}")

        g.close()


if __name__ == "__main__":
    main()
