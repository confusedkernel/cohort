"""The terminal front end, deliberately the same surface as the web one.

COHORT is meant to be usable two ways — as a Python library by people who write
Python, and as a tool by researchers who don't. That promise is only kept if
the two front ends can do the same things, so every command here corresponds to
a route in `cohort/ui/api.py`, and `tests/test_parity.py` fails the build if one
gains a capability the other lacks. Where a correspondence is deliberately not
one-to-one, the exemption is written down there rather than left to be noticed.

Both front ends sit on the same library calls. Neither reimplements a rule:
`accept` here and `POST /api/accept` both call `Graph.accept()`, so the write
boundary refuses identically whichever way you reach it.

    cohort health
    cohort graph --type claim
    cohort node claim:abc123
    cohort accept claim:abc123
    cohort reject claim:abc123 --reason "conflates two recensions"
    cohort refusals
    cohort rebuild
    cohort search 色即是空
    cohort run --agent "find attestations for 色即是空" --budget 0.05

`--json` on any command prints exactly what the corresponding HTTP route
returns, which is what makes the parity claim checkable rather than asserted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .errors import (
    CohortError,
    EdgeNotFound,
    NodeNotFound,
    RebuildMismatch,
    SingleWriterViolation,
)
from .eventlog import EventLog, read_refusals
from .graph import Graph
from .schemas import RESEARCHER, NodeType
from .views import edge_json, node_detail_json, node_json

DEFAULT_DB = "demo_graph.sqlite"


# --- plumbing ---------------------------------------------------------------

def _log_path(args) -> Path:
    """Default the event log beside the projection, same rule the server uses."""
    return Path(args.log) if args.log else Path(args.db).with_suffix(".jsonl")


def _read(args) -> Graph:
    """A reader's handle: no writer lock, so this works while a run is writing."""
    db = Path(args.db)
    if not db.is_file():
        raise SystemExit(
            f"no graph at {db}. Build one with scripts/seed_demo_graph.py, "
            f"or point at another with --db"
        )
    return Graph.open_read_only(db)


def _write(args) -> Graph:
    """A writer's handle, held for one command. If an agent run holds the lock
    this raises rather than waiting — the same answer the API gives as a 409."""
    return Graph(Path(args.db), event_log=EventLog(_log_path(args)))


def _emit(args, payload: Any, render) -> None:
    """`--json` prints the API's own shape; otherwise render for a human."""
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        render(payload)


def _corpus(args):
    from .sources.env import open_corpus_from_env
    source, reason = open_corpus_from_env(repo_root=Path.cwd())
    if source is None:
        raise SystemExit(f"corpus unavailable: {reason}")
    return source


# --- read commands ----------------------------------------------------------

def cmd_health(args) -> None:
    graph = _read(args)
    try:
        counts = {
            r["type"]: r["c"]
            for r in graph.conn.execute("SELECT type, COUNT(*) c FROM nodes GROUP BY type")
        }
        edges = graph.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
    finally:
        graph.close()
    payload = {"ok": True, "db_path": args.db, "nodes": counts, "edges": edges}

    def render(p):
        print(f"{p['db_path']}  —  {sum(p['nodes'].values())} nodes, {p['edges']} edges")
        for t, n in sorted(p["nodes"].items(), key=lambda kv: -kv[1]):
            print(f"  {n:>6}  {t}")
    _emit(args, payload, render)


def cmd_graph(args) -> None:
    graph = _read(args)
    try:
        node_type = NodeType(args.type) if args.type else None
        nodes = graph.nodes(node_type=node_type, limit=args.limit + 1)
        truncated = len(nodes) > args.limit
        nodes = nodes[: args.limit]
        ids = {n.id for n in nodes}
        edges = [
            e for e in graph.edges(include_retracted=args.include_retracted)
            if e.src in ids and e.dst in ids
        ]
        payload = {
            "nodes": [node_json(graph, n) for n in nodes],
            "edges": [edge_json(e) for e in edges],
            "truncated": truncated,
        }
    finally:
        graph.close()

    def render(p):
        for n in p["nodes"]:
            print(f"{n['status']:<9} {n['type']:<12} {n['id']}")
        print(f"\n{len(p['nodes'])} nodes, {len(p['edges'])} edges", end="")
        # Truncation is stated, never silent: a cut graph shows less support
        # than exists, which here changes what the result appears to say.
        print("  (TRUNCATED — pass --limit for more)" if p["truncated"] else "")
    _emit(args, payload, render)


def cmd_node(args) -> None:
    graph = _read(args)
    try:
        payload = node_detail_json(graph, args.id)
    except NodeNotFound as e:
        raise SystemExit(str(e))
    finally:
        graph.close()

    def render(p):
        print(f"{p['id']}\n  type       {p['type']}\n  status     {p['status']}")
        print(f"  assurance  {p['assurance']}")
        if p.get("rejected_reason"):
            print(f"  rejected   {p['rejected_reason']}")
        for k, v in (p.get("payload") or {}).items():
            print(f"  {k:<10} {v}")
        sup = p.get("independent_support")
        if sup:
            # The whole argument in one line: a support count means nothing
            # without the independence flag beside it.
            flag = "independent" if sup["independent"] else "NOT independent (shared descent)"
            print(f"  support    {sup['attesting_count']} attesting, "
                  f"{sup['distinct_witnesses']} distinct witness(es) — {flag}")
            for a, b in sup["non_independent_pairs"]:
                print(f"             discounted: {a} ~ {b}")
        for v in p["verifications"]:
            pl = v["payload"]
            print(f"  verified   {pl['method']} -> {pl['result']} | {pl['assurance_level']}")
        for e in p["edges_out"]:
            print(f"  --{e['type']}--> {e['dst']}")
        for e in p["edges_in"]:
            print(f"  <--{e['type']}-- {e['src']}")
    _emit(args, payload, render)


def cmd_citable(args) -> None:
    graph = _read(args)
    try:
        payload = [node_json(graph, n) for n in graph.citable()]
    finally:
        graph.close()

    def render(p):
        if not p:
            # Not an error, and worth saying plainly: nothing is citable until
            # the researcher signs it, so an empty list is the normal state.
            print("nothing is citable yet — only accepted nodes are, and none are accepted")
            return
        for n in p:
            print(f"{n['type']:<12} {n['id']}")
        print(f"\n{len(p)} citable")
    _emit(args, payload, render)


def cmd_rejected(args) -> None:
    graph = _read(args)
    try:
        node_type = NodeType(args.type) if args.type else None
        payload = [node_json(graph, n) for n in graph.rejected(node_type=node_type)]
    finally:
        graph.close()

    def render(p):
        # Rejections with reasons are part of the scholarly output, not a
        # failure list (docs/design.md §8).
        for n in p:
            print(f"{n['type']:<12} {n['id']}\n    {n.get('rejected_reason') or '(no reason recorded)'}")
        print(f"\n{len(p)} rejected")
    _emit(args, payload, render)


def cmd_agent(args) -> None:
    graph = _read(args)
    try:
        payload = graph.agent_report(args.id).model_dump(mode="json")
        profile = graph.agent_profile(args.id)
        payload["profile"] = profile.model_dump(mode="json") if profile else None
    finally:
        graph.close()

    def render(p):
        print(f"{args.id}")
        if p.get("profile"):
            pr = p["profile"]
            print(f"  scope      {pr.get('corpus_scope') or '—'}")
            print(f"  method     {pr.get('method_label') or '—'}")
        for k, v in p.items():
            if k != "profile" and not isinstance(v, (dict, list)):
                print(f"  {k:<10} {v}")
        # Counts, never a score — see docs/design.md §9.
        print("\n  contribution counts, not a reputation score")
    _emit(args, payload, render)


def cmd_refusals(args) -> None:
    log = _log_path(args)
    if not log.is_file():
        payload = {"available": False, "log_path": str(log), "refusals": [], "total": 0}
    else:
        allr = read_refusals(log)
        shown = allr[-args.limit:]
        payload = {
            "available": True, "log_path": str(log), "total": len(allr),
            "truncated": len(shown) < len(allr),
            "refusals": [r.model_dump(mode="json") for r in shown],
        }

    def render(p):
        if not p["available"]:
            print(f"no event log at {p['log_path']}, so refusals cannot be read")
            return
        for r in p["refusals"]:
            print(f"#{r['seq']:<5} {r['attempted']:<12} {r['rule']}\n      {r['message']}")
        # A zero here is a fact, not an absence of news.
        print(f"\n{p['total']} refused write(s) — the write boundary holding, not failures")
    _emit(args, payload, render)


def cmd_integrity(args) -> None:
    graph = _read(args)
    try:
        payload = graph.verify_integrity(args.id).model_dump(mode="json")
    finally:
        graph.close()

    def render(p):
        print(f"checked {p['checked']} node payload(s)")
        print(f"  mismatched {len(p['mismatched'])}   unhashed {len(p['unhashed'])}")
        for i in p["mismatched"]:
            print(f"  TAMPERED  {i}")
    _emit(args, payload, render)


def cmd_rebuild(args) -> None:
    log = _log_path(args)
    if not log.is_file():
        payload = {"available": False, "log_path": str(log)}
    else:
        graph = _read(args)
        try:
            payload = {"available": True, "log_path": str(log),
                       **graph.rebuild(log_path=log).model_dump(mode="json")}
        except RebuildMismatch as e:
            payload = {"available": True, "log_path": str(log), "ok": False, "mismatch": str(e)}
        finally:
            graph.close()

    def render(p):
        if not p["available"]:
            print(f"no event log at {p['log_path']}, so the projection cannot be checked")
            return
        if p.get("ok"):
            print(f"OK — replayed {p['events_replayed']} events to "
                  f"{p['nodes']} nodes / {p['edges']} edges, matching this projection")
        else:
            # The log is ground truth, so a mismatch means the database is
            # wrong, not the log (docs/design.md §5 principle 1).
            print("MISMATCH — the projection disagrees with the log, which is ground truth:")
            print(p["mismatch"])
    _emit(args, payload, render)


# --- write commands ---------------------------------------------------------

def _verdict(args, action: str) -> None:
    try:
        graph = _write(args)
    except SingleWriterViolation as e:
        # Same answer the API gives as a 409, phrased for a terminal.
        raise SystemExit(f"the graph is locked by another writer (an agent run?): {e}")
    try:
        kwargs: dict[str, Any] = {"authored_by": RESEARCHER}
        if action in ("reject", "reopen"):
            kwargs["reason"] = args.reason
        if action == "attest":
            # Not a verdict: the write boundary runs the mechanical check and
            # refuses if the node has nothing attesting it. No decision node.
            graph.attest(args.id, **kwargs)
            decision_id = None
        else:
            method = {"accept": graph.accept, "reject": graph.reject,
                      "reopen": graph.reopen}[action]
            decision_id = method(args.id, **kwargs)
        payload = {"node": node_json(graph, graph.get_node(args.id)),
                   "decision_node_id": decision_id}
    except NodeNotFound as e:
        raise SystemExit(str(e))
    except CohortError as e:
        # A refused write is a real answer from this system, already recorded
        # to the log. Exit 2 distinguishes it from a usage error.
        print(f"refused ({type(e).__name__}): {e}", file=sys.stderr)
        raise SystemExit(2)
    finally:
        graph.close()

    _emit(args, payload, lambda p: print(f"{p['node']['id']} -> {p['node']['status']}"))


def _edge_verdict(args, action: str) -> None:
    try:
        graph = _write(args)
    except SingleWriterViolation as e:
        raise SystemExit(f"the graph is locked by another writer (an agent run?): {e}")
    try:
        method = graph.retract_edge if action == "retract" else graph.restore_edge
        method(args.id, authored_by=RESEARCHER, reason=args.reason)
        edge = next(e for e in graph.edges(include_retracted=True) if e.id == args.id)
        payload = {"edge": edge_json(edge)}
    except EdgeNotFound as e:
        raise SystemExit(str(e))
    except CohortError as e:
        print(f"refused ({type(e).__name__}): {e}", file=sys.stderr)
        raise SystemExit(2)
    finally:
        graph.close()

    def render(p):
        e = p["edge"]
        state = "retracted" if e["retracted"] else "in force"
        print(f"{e['type']} {e['src']} -> {e['dst']}  ->  {state}")
        if e["retracted_reason"]:
            print(f"  {e['retracted_reason']}")
    _emit(args, payload, render)


def cmd_retract_edge(args) -> None:
    _edge_verdict(args, "retract")


def cmd_restore_edge(args) -> None:
    _edge_verdict(args, "restore")


def cmd_attest(args) -> None:
    _verdict(args, "attest")


def cmd_accept(args) -> None:
    _verdict(args, "accept")


def cmd_reject(args) -> None:
    _verdict(args, "reject")


def cmd_reopen(args) -> None:
    _verdict(args, "reopen")


# --- corpus commands --------------------------------------------------------

def cmd_search(args) -> None:
    source = _corpus(args)
    hits = source.search(args.query, max_results=args.limit)
    payload = {
        "query": args.query, "count": len(hits),
        "ordering": "corpus order; no relevance ranking",
        "truncated": len(hits) >= args.limit,
        "hits": [h.model_dump(mode="json") for h in hits],
    }

    def render(p):
        for h in p["hits"]:
            print(f"{h['ref']}\n    {h.get('snippet', '')}")
        print(f"\n{p['count']} hit(s) — {p['ordering']}")
    _emit(args, payload, render)


def cmd_fetch(args) -> None:
    source = _corpus(args)
    record = source.fetch(args.ref)
    text = record.text[: args.max_chars]
    if args.strip_markup:
        from .sources.cbeta_markup import strip_markup_for_display
        text = strip_markup_for_display(text)
    payload = {
        "ref": args.ref, "witness_ref": record.witness_ref, "title": record.title,
        "locator": record.locator, "source_terms": record.note,
        "truncated": len(record.text) > args.max_chars, "text": text,
    }

    def render(p):
        print(f"{p['witness_ref']}  {p['title'] or ''}")
        # The licence rides with the text, here as everywhere else.
        if p.get("source_terms"):
            print(f"terms: {p['source_terms']}")
        print()
        print(p["text"])
        if p["truncated"]:
            print("\n… truncated; raise --max-chars for more")
    _emit(args, payload, render)


# --- agent runs -------------------------------------------------------------

def cmd_run(args) -> None:
    """Start a run and wait for it. The web launcher is asynchronous because a
    browser cannot block; a terminal can, so this stays in the foreground and
    Ctrl-C is the stop button."""
    from .ui.runs import AgentSpec, RunManager, RunRejected

    source = _corpus(args)
    models = args.model or []
    if models and len(models) != len(args.agent):
        raise SystemExit(
            f"{len(args.agent)} --agent but {len(models)} --model: give one model "
            "per agent, or none and they all use the configured default "
            "(which a multi-agent run will then refuse, since agents in one run "
            "may not share a model family)."
        )
    specs = [
        AgentSpec(agent_id=f"agent:cli-{i + 1}", instructions=text,
                  corpus_scope=args.scope or "", method_label=args.method or "",
                  model=models[i] if models else "")
        for i, text in enumerate(args.agent)
    ]
    manager = RunManager(
        Path(args.db), _log_path(args), source,
        max_budget_usd=args.budget, max_turns=args.max_turns,
    )
    try:
        manager.start(specs, budget_usd=args.budget, max_turns=args.max_turns)
    except RunRejected as e:
        raise SystemExit(f"refused: {e}")

    async def wait() -> dict[str, Any] | None:
        """Poll the same way the browser does — `current()`/`history()` are the
        run manager's whole status surface, and `GET /api/run` is these two."""
        while True:
            current = manager.current()
            if not current or current["state"] not in ("starting", "running"):
                return current
            await asyncio.sleep(0.5)

    try:
        run = asyncio.run(wait())
    except KeyboardInterrupt:
        manager.stop()
        raise SystemExit("\nstopping after this turn…")

    if run is None:
        history = manager.history(limit=1)
        run = history[0] if history else {}

    def render(p):
        r = p
        spend = r.get("spend", {})
        print(f"{r.get('state')}  {r.get('elapsed_s')}s  "
              f"${spend.get('spent_usd', 0):.5f} of ${spend.get('budget_usd', 0):.2f}"
              f"  {spend.get('calls', 0)} call(s)")
        for a in r.get("agents", []):
            print(f"\n{a['agent_id']}")
            if a.get("error"):
                print(f"  error: {a['error']}")
            for c in a.get("tool_calls", []):
                mark = "refused" if c.get("is_error") else "ok"
                print(f"  [{mark}] {c['tool']}: {str(c.get('result'))[:120]}")
        if r.get("error"):
            print(f"\nrun error: {r['error']}")
    _emit(args, run, render)


# --- parser -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cohort",
        description="COHORT from the terminal — the same capabilities as the web UI.",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help=f"graph projection (default {DEFAULT_DB})")
    parser.add_argument("--log", default=None, help="event log (default: --db with .jsonl)")
    parser.add_argument("--json", action="store_true", help="print the API's own JSON shape")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(func=fn)
        return p

    add("health", cmd_health, "node and edge counts")

    p = add("graph", cmd_graph, "list nodes and the edges between them")
    p.add_argument("--type", choices=[t.value for t in NodeType])
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--include-retracted", action="store_true",
                   help="also show edges the researcher has withdrawn")

    p = add("node", cmd_node, "one node with its full provenance")
    p.add_argument("id")

    add("citable", cmd_citable, "accepted nodes — the only ones citable by output")

    p = add("rejected", cmd_rejected, "rejected nodes, with their reasons")
    p.add_argument("--type", choices=[t.value for t in NodeType])

    p = add("agent", cmd_agent, "an agent's contribution counts")
    p.add_argument("id")

    p = add("refusals", cmd_refusals, "writes the graph refused, and which rule refused them")
    p.add_argument("--limit", type=int, default=100)

    p = add("integrity", cmd_integrity, "re-hash stored payloads against their recorded hashes")
    p.add_argument("--id", default=None, help="check one node instead of all")

    add("rebuild", cmd_rebuild, "replay the log and diff it against this projection")

    p = add("attest", cmd_attest, "run the mechanical check: do this node's citations resolve?")
    p.add_argument("id")

    p = add("accept", cmd_accept, "promote a node to accepted (as the researcher)")
    p.add_argument("id")

    p = add("reject", cmd_reject, "reject a node, with a reason (as the researcher)")
    p.add_argument("id")
    p.add_argument("--reason", required=True)

    p = add("reopen", cmd_reopen, "reopen a rejected node (as the researcher)")
    p.add_argument("id")
    p.add_argument("--reason", required=True)

    p = add("retract-edge", cmd_retract_edge,
            "withdraw an edge, with a reason (as the researcher)")
    p.add_argument("id")
    p.add_argument("--reason", required=True)

    p = add("restore-edge", cmd_restore_edge,
            "undo a retraction, with a reason (as the researcher)")
    p.add_argument("id")
    p.add_argument("--reason", required=True)

    p = add("search", cmd_search, "search the corpus")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)

    p = add("fetch", cmd_fetch, "fetch one corpus record")
    p.add_argument("ref")
    p.add_argument("--max-chars", type=int, default=8000)
    p.add_argument("--strip-markup", action="store_true",
                   help="display only — this breaks offsets, so never store the result")

    p = add("run", cmd_run, "run one or more agents against the graph (spends money)")
    p.add_argument("--agent", action="append", required=True, metavar="INSTRUCTIONS",
                   help="repeat for several agents")
    p.add_argument("--model", action="append", metavar="MODEL",
                   help="one per --agent; agents in a run may not share a model family")
    p.add_argument("--scope", default=None, help="declared corpus scope")
    p.add_argument("--method", default=None, help="declared method")
    p.add_argument("--budget", type=float, default=0.25, help="hard USD cap for the run")
    p.add_argument("--max-turns", type=int, default=8)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
