"""Serve the researcher UI against a graph projection (build order stage 5).

Reads never take the writer lock, so this is safe to run while an agent run
is writing to the same graph (see `cohort/ui/api.py`).

`--allow-writes` additionally mounts the researcher's accept/reject/reopen
endpoints. Off by default, for two reasons: the read-only deployment stays the
default, and those endpoints act as `RESEARCHER`, the one privileged identity
in the promotion ladder. Passing the flag is the operator asserting that
whoever can reach this port is the researcher. Each write holds the exclusive
lock for one request only; if an agent run holds it, the endpoint answers 409
rather than waiting.

Binds 127.0.0.1 by default and deliberately: this is a shared lab machine, and
the corpus behind the graph is licensed CC BY-NC-SA-equivalent, so the default
must not publish it to the network. Over SSH, forward the port instead
(VS Code does this automatically; otherwise `ssh -L 8000:localhost:8000 ...`).

`--corpus` mounts corpus browse/search, and `--allow-runs` mounts the agent
run launcher. Together with `--allow-writes` they make the web UI reach parity
with the Python API: search the corpus, start a run, watch its spend and its
refusals, accept or reject the result. Each is opt-in separately because they
carry different consequences — reading the corpus is free, accepting a finding
is a scholarly act, and starting a run spends money.

Usage:
    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite
    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite --port 8010

    # everything the Python API can do, from the browser:
    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite \
        --corpus --allow-writes --allow-runs --max-budget 0.50
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cohort.ui.runs import DEFAULT_MAX_BUDGET_USD

REPO_ROOT = Path(__file__).resolve().parent.parent

CBETA_V061_SHA256 = "90a663f212bc854e6a758ed06c74776cef5cbf8e7040d0192ff3301e6f7158f2"


def _open_corpus():
    """The same reader the scripts build, from the same environment — so a
    query in the browser and a query in Python hit one index, not two.

    Returns None with an explanation rather than raising: the UI is useful
    without the corpus (the graph is already there), so a missing archive
    should degrade the feature, not refuse to start the server."""
    from cohort.agents.openrouter import _load_dotenv
    from cohort.sources.cbeta_fts import CbetaFtsIndex
    from cohort.sources.cbeta_reader import CbetaArchiveError, CbetaReader

    _load_dotenv(REPO_ROOT / ".env")
    archive = os.environ.get("CBETA_ARCHIVE_PATH")
    if not archive:
        print("note: CBETA_ARCHIVE_PATH is not set — corpus endpoints disabled", file=sys.stderr)
        return None
    fts_path = Path(os.environ.get("CBETA_FTS_PATH") or (REPO_ROOT / "cbeta_fts.sqlite"))
    try:
        fts = CbetaFtsIndex(fts_path, CBETA_V061_SHA256) if fts_path.is_file() else None
        if fts is None:
            print(
                f"note: no FTS index at {fts_path} — corpus search would raise, so "
                "corpus endpoints are disabled.\n"
                "      build it: .venv/bin/python scripts/build_cbeta_index.py",
                file=sys.stderr,
            )
            return None
        return CbetaReader(archive, CBETA_V061_SHA256, fts=fts)
    except CbetaArchiveError as e:
        print(f"note: corpus endpoints disabled — {e}", file=sys.stderr)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(REPO_ROOT / "demo_graph.sqlite"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--allow-writes", action="store_true",
        help="mount the researcher's accept/reject/reopen endpoints (acts as RESEARCHER)",
    )
    parser.add_argument(
        "--log", default=None,
        help="event log path (default: the --db path with a .jsonl suffix)",
    )
    parser.add_argument(
        "--corpus", action="store_true",
        help="mount corpus browse/search (needs CBETA_ARCHIVE_PATH and CBETA_FTS_PATH)",
    )
    parser.add_argument(
        "--allow-runs", action="store_true",
        help="mount the agent run launcher — these endpoints spend money (implies --corpus)",
    )
    parser.add_argument(
        "--max-budget", type=float, default=DEFAULT_MAX_BUDGET_USD,
        help=(
            f"hard per-run USD ceiling the browser cannot raise "
            f"(default {DEFAULT_MAX_BUDGET_USD:.2f})"
        ),
    )
    args = parser.parse_args()

    try:
        import uvicorn
    except ModuleNotFoundError:
        print(
            "the `ui` extra is not installed: .venv/bin/pip install -e '.[ui]'",
            file=sys.stderr,
        )
        sys.exit(1)

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"no graph projection at {db_path}", file=sys.stderr)
        print("build one first: .venv/bin/python scripts/seed_demo_graph.py", file=sys.stderr)
        sys.exit(1)

    from cohort.ui.api import FRONTEND_DIR, create_app
    from cohort.ui.runs import RunManager

    source = None
    if args.corpus or args.allow_runs:
        source = _open_corpus()
        if source is None and args.allow_runs:
            print(
                "error: --allow-runs needs a corpus, but none could be opened "
                "(see the message above)",
                file=sys.stderr,
            )
            sys.exit(1)

    run_manager = None
    if args.allow_runs:
        log_path = Path(args.log) if args.log else db_path.with_suffix(".jsonl")
        run_manager = RunManager(
            db_path, log_path, source, max_budget_usd=args.max_budget,
        )

    if not FRONTEND_DIR.is_dir():
        print(
            f"note: no built frontend at {FRONTEND_DIR} — serving the JSON API only.\n"
            "      build it with: cd cohort/ui/frontend && npm install && npm run build",
            file=sys.stderr,
        )

    if args.host not in ("127.0.0.1", "localhost"):
        print(
            f"warning: binding {args.host} exposes a CC BY-NC-SA-licensed corpus "
            "view beyond this machine",
            file=sys.stderr,
        )

    modes = ["read-only"]
    if args.allow_writes:
        modes.append("researcher writes")
    if source is not None:
        modes.append("corpus")
    if run_manager is not None:
        modes.append(f"agent runs (max ${args.max_budget:.2f}/run)")
    mode = " + ".join(modes)
    print(f"serving {db_path} at http://{args.host}:{args.port} ({mode})")
    if args.allow_writes:
        print(
            "  writes enabled: accept/reject/reopen act as RESEARCHER, and take the "
            "writer lock\n  for one request each (409 while an agent run holds it)"
        )
    if run_manager is not None:
        cfg = run_manager.config()
        if not cfg["model_configured"]:
            print(f"  warning: {cfg['config_error']} — runs will be refused", file=sys.stderr)
        else:
            print(f"  agent runs enabled: model {cfg['model']}, ceiling ${args.max_budget:.2f} per run")
            print("  every run is capped in code and stops before the call that would exceed it")

    uvicorn.run(
        create_app(
            db_path, args.log, allow_writes=args.allow_writes,
            source=source, run_manager=run_manager,
        ),
        host=args.host, port=args.port,
    )


if __name__ == "__main__":
    main()
