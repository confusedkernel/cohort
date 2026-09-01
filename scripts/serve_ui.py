"""Serve the researcher UI against a graph projection (build order stage 5).

Read-only: the server never takes the writer lock, so it is safe to run while
an agent run is writing to the same graph (see `cohort/ui/api.py`).

Binds 127.0.0.1 by default and deliberately: this is a shared lab machine, and
the corpus behind the graph is licensed CC BY-NC-SA-equivalent, so the default
must not publish it to the network. Over SSH, forward the port instead
(VS Code does this automatically; otherwise `ssh -L 8000:localhost:8000 ...`).

Usage:
    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite
    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite --port 8010
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(REPO_ROOT / "demo_graph.sqlite"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
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

    print(f"serving {db_path} at http://{args.host}:{args.port} (read-only)")
    uvicorn.run(create_app(db_path), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
