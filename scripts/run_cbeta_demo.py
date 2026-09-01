"""Manual live demonstration of find_attestations against the real CBETA
archive (HANDOFF.md "suggested first session", step 4) — the first time
this project has run an agent against real Buddhist text rather than the
Tang-poem fixture.

Never imported by pytest, never run automatically — same discipline as
`scripts/smoke_openrouter.py` and `scripts/run_swarm_demo.py`.

Uses a hand-maintained `entry_path -> known excerpts` index (HANDOFF.md's
suggested minimal approach — not a full-corpus index), loaded from a local
JSON file that is gitignored because its excerpts are corpus bytes.

Usage:
    .venv/bin/python scripts/run_cbeta_demo.py

Requires CBETA_ARCHIVE_PATH, OPENROUTER_API_KEY and OPENROUTER_MODEL in
`.env` (see .env.example and HANDOFF.md).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from cohort.agents.attestation_worker import AttestationWorker
from cohort.agents.openrouter import OpenRouterError, _load_dotenv
from cohort.graph import Graph
from cohort.schemas import AgentKind, AgentProfile, ClaimPayload
from cohort.sources.cbeta_reader import CbetaArchiveError, CbetaReader

#: the archive version this SHA-256 identifies — not corpus bytes, a fact
#: about which version was verified (HANDOFF.md, re-verified independently
#: against the actual file before this script existed).
CBETA_V061_SHA256 = "90a663f212bc854e6a758ed06c74776cef5cbf8e7040d0192ff3301e6f7158f2"

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_PATH = REPO_ROOT / "cbeta_index.json"

AGENT = "agent:worker-cbeta-1"


def main() -> None:
    _load_dotenv(REPO_ROOT / ".env")

    archive_path = os.environ.get("CBETA_ARCHIVE_PATH")
    if not archive_path:
        print("config error: CBETA_ARCHIVE_PATH is not set (see .env.example, HANDOFF.md)", file=sys.stderr)
        sys.exit(1)

    if not DEFAULT_INDEX_PATH.is_file():
        print(f"config error: no index file at {DEFAULT_INDEX_PATH}", file=sys.stderr)
        sys.exit(1)
    index = json.loads(DEFAULT_INDEX_PATH.read_text(encoding="utf-8"))

    try:
        source = CbetaReader(archive_path, CBETA_V061_SHA256, index=index)
    except CbetaArchiveError as e:
        print(f"archive error: {e}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="cohort_cbeta_demo_") as tmp:
        tmp_path = Path(tmp)
        graph = Graph.open(tmp_path / "graph.sqlite", tmp_path / "events.jsonl")

        graph.register_agent(
            AgentProfile(
                id=AGENT, kind=AgentKind.WORKER,
                corpus_scope="CBETA v061: Heart Sutra (T251) and Diamond Sutra (T235)",
                method_label="direct textual attestation",
            ),
            authored_by=AGENT,
        )

        claim_heart = graph.propose_claim(
            ClaimPayload(text="The Heart Sutra (Taisho T251) states that form is emptiness and emptiness is form"),
            authored_by=AGENT,
        )
        claim_diamond = graph.propose_claim(
            ClaimPayload(
                text="The Diamond Sutra (Taisho T235) closes with a gatha comparing all "
                "conditioned phenomena to a dream, illusion, bubble, and shadow"
            ),
            authored_by=AGENT,
        )

        try:
            worker = AttestationWorker(graph, source=source, authored_by=AGENT, profile=graph.agent_profile(AGENT))
        except OpenRouterError as e:
            print(f"config error: {e}", file=sys.stderr)
            graph.close()
            sys.exit(1)

        instructions = (
            f"Find attestations for claim {claim_heart!r} using the query 色即是空, "
            f"then find attestations for claim {claim_diamond!r} using the query 如夢幻泡影, "
            "then stop."
        )

        print("Running one agent against the real CBETA v061 archive via OpenRouter...\n")
        log = worker.run(instructions)

        for entry in log:
            status = "error" if entry["is_error"] else "ok"
            print(f"  {entry['tool']} -> {status}: {entry['result']}")

        report = graph.agent_report(AGENT)
        print(f"\nagent_report: proposed={report.proposed} attested={report.attested} "
              f"accepted={report.accepted} rejected={report.rejected}")

        graph.close()


if __name__ == "__main__":
    main()
