"""Read-only JSON API over the evidence graph (build order stage 5).

**Reads never take the writer lock.** Every read endpoint opens the
projection through `Graph.open_read_only()`, which takes no lock and cannot
write (SQLite `mode=ro`, no `EventLog` attached), so the API keeps serving
while an agent run is writing.

**Writes are opt-in, and hold the lock for one request only.** The
researcher's accept/reject (DESIGN.md §13 stage 5) lives here now, behind
`allow_writes`. An earlier version of this docstring argued a writing UI
would have to hold the exclusive lock "for as long as a browser tab is
open" — that was never actually required. Each write endpoint calls
`Graph.open()` for the duration of one request and closes it, so the lock is
held for milliseconds, not for a session. Single-writer discipline is
therefore unchanged, not relaxed: if an agent run holds the lock, `flock`
refuses, and the endpoint answers `409 Conflict` saying so, rather than
queueing, retrying, or (worst) weakening the lock.

Writes default to **off** so the read-only deployment stays the default, and
because these endpoints act as `RESEARCHER` — the one identity the promotion
ladder treats as privileged (DESIGN.md §8, "Only the researcher"). Enabling
them is the operator asserting that whoever can reach this port *is* the
researcher, which is a claim only the operator can make.

**What the API must not flatten.** DESIGN.md §10 warns that a naive
projection of this graph into a knowledge graph "flattens exactly the
epistemics that justify the system": if the view shows nodes without status
and edges without the independence flag, it silently restores the consensus
illusion, because a densely-linked node then looks well-supported regardless
of whether its support is independent. So `/graph` returns node `status` and
edge `type` on every element rather than leaving the frontend to fetch them,
and `discounts` marks the edge types (`descends_from`, `parallel_of`) that
*reduce* support instead of adding it. The frontend is then able to render the
distinction — this layer at least makes it impossible to omit by accident.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..errors import CohortError, NodeNotFound, SingleWriterViolation
from ..eventlog import read_refusals
from ..graph import Graph
from ..schemas import RESEARCHER, EdgeType, NodeType

#: edge types that *discount* support rather than add it (DESIGN.md §4): two
#: witnesses linked by either are evidence of shared descent, not independent
#: confirmation. Named here so the frontend never has to re-derive it.
DISCOUNTING_EDGE_TYPES = frozenset({EdgeType.DESCENDS_FROM, EdgeType.PARALLEL_OF})

FRONTEND_DIR = Path(__file__).resolve().parent / "static"


def _node_json(graph: Graph, node) -> dict[str, Any]:
    return {
        "id": node.id,
        "type": node.type,
        "status": node.status,
        "payload": node.payload,
        "rejected_reason": node.rejected_reason,
        "authorship": [a.model_dump(mode="json") for a in node.authorship],
        "created_seq": node.created_seq,
        "updated_seq": node.updated_seq,
        "assurance": graph.assurance_for(node.id),
    }


def _edge_json(edge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "type": edge.type,
        "src": edge.src,
        "dst": edge.dst,
        "discounts": edge.type in DISCOUNTING_EDGE_TYPES,
        "reason": edge.reason,
        "authorship": [a.model_dump(mode="json") for a in edge.authorship],
        "created_seq": edge.created_seq,
    }


def create_app(
    db_path: str | Path,
    log_path: str | Path | None = None,
    *,
    allow_writes: bool = False,
) -> FastAPI:
    """Build the app around one projection path.

    A fresh read-only `Graph` is opened per request rather than held open for
    the app's lifetime. That is deliberate: an agent run writing to the same
    file advances it constantly, and a long-lived connection would serve a
    snapshot that silently ages. It also keeps sqlite3's same-thread rule
    satisfied without pinning the server to one worker.

    `log_path` defaults to `db_path` with a `.jsonl` suffix, the convention
    every script already uses. It is needed for `/api/refusals`, which reads
    the event log directly: a refused write changed no graph state, so there
    is nothing in the SQLite projection to read it from.

    `allow_writes` mounts the researcher's accept/reject endpoints. Off by
    default — see this module's docstring."""
    db_path = Path(db_path)
    log_path = Path(log_path) if log_path is not None else db_path.with_suffix(".jsonl")
    app = FastAPI(
        title="COHORT",
        summary="Read-only view of the evidence graph.",
        version="0.1.0",
    )

    def read() -> Graph:
        try:
            return Graph.open_read_only(db_path)
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        graph = read()
        try:
            counts: dict[str, int] = {}
            for row in graph.conn.execute("SELECT type, COUNT(*) c FROM nodes GROUP BY type"):
                counts[row["type"]] = row["c"]
            edges = graph.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
            return {
                "ok": True, "db_path": str(db_path), "nodes": counts, "edges": edges,
                "writes_enabled": allow_writes,
            }
        finally:
            graph.close()

    @app.get("/api/graph")
    def graph_view(
        node_type: NodeType | None = Query(default=None),
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> dict[str, Any]:
        """Nodes and edges for the graph view.

        `truncated` is reported explicitly: a silently cut graph would show
        fewer supporting witnesses than exist, which in this system is not a
        cosmetic omission — it changes what the picture appears to say about
        support."""
        graph = read()
        try:
            # fetch one extra to detect truncation without a second COUNT query
            nodes = graph.nodes(node_type=node_type, limit=limit + 1)
            truncated = len(nodes) > limit
            nodes = nodes[:limit]
            ids = {n.id for n in nodes}
            edges = [e for e in graph.edges() if e.src in ids and e.dst in ids]
            return {
                "nodes": [_node_json(graph, n) for n in nodes],
                "edges": [_edge_json(e) for e in edges],
                "truncated": truncated,
                "discounting_edge_types": sorted(DISCOUNTING_EDGE_TYPES),
            }
        finally:
            graph.close()

    @app.get("/api/node")
    def node_detail(id: str = Query(..., min_length=1)) -> dict[str, Any]:
        """One node with everything needed for provenance on click: its
        payload and authorship, its verifications, its edges in both
        directions, and — for a claim or conjecture — the independence of its
        support.

        The id is a **query parameter, not a path segment**, because node ids
        are opaque and routinely contain `#`: a passage's canonical ref is
        `{witness}#{excerpt}`. In a path, `#` starts the fragment and never
        reaches the server, so `/api/nodes/passage:T08n0250#...` silently
        arrives as a request for `passage:T08n0250` and 404s. A query
        parameter is the ordinary place for an opaque value, and every URL
        builder percent-encodes it correctly."""
        node_id = id
        graph = read()
        try:
            try:
                node = graph.get_node(node_id)
            except NodeNotFound as e:
                raise HTTPException(status_code=404, detail=str(e)) from e

            detail = _node_json(graph, node)
            detail["verifications"] = [
                _node_json(graph, v) for v in graph.verifications(node_id)
            ]
            detail["edges_out"] = [_edge_json(e) for e in graph.edges(src=node_id)]
            detail["edges_in"] = [_edge_json(e) for e in graph.edges(dst=node_id)]
            if node.type in (NodeType.CLAIM, NodeType.CONJECTURE):
                detail["independent_support"] = graph.independent_support(
                    node_id
                ).model_dump(mode="json")
            return detail
        finally:
            graph.close()

    @app.get("/api/citable")
    def citable() -> list[dict[str, Any]]:
        graph = read()
        try:
            return [_node_json(graph, n) for n in graph.citable()]
        finally:
            graph.close()

    @app.get("/api/rejected")
    def rejected(node_type: NodeType | None = Query(default=None)) -> list[dict[str, Any]]:
        graph = read()
        try:
            return [_node_json(graph, n) for n in graph.rejected(node_type=node_type)]
        finally:
            graph.close()

    @app.get("/api/agent")
    def agent_report(id: str = Query(..., min_length=1)) -> dict[str, Any]:
        """Query parameter for the same reason as `/api/node`: agent ids are
        opaque strings (`agent:worker-heart`) and must survive encoding."""
        agent_id = id
        graph = read()
        try:
            report = graph.agent_report(agent_id).model_dump(mode="json")
            profile = graph.agent_profile(agent_id)
            report["profile"] = profile.model_dump(mode="json") if profile else None
            return report
        finally:
            graph.close()

    @app.get("/api/refusals")
    def refusals(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
        """The refused writes, most recent last.

        This is an output surface, not a debug view: DESIGN.md §15 claims the
        system's "refusals are part of its scholarly output", and until this
        endpoint existed they were visible only in `demo.py`'s terminal
        printout. Read from the event log rather than the projection —
        a refusal changed no state, so there is no row for it.

        A missing log is not an error: an in-memory or freshly copied
        projection can legitimately have none, and reporting `available:
        false` says that honestly instead of implying zero refusals."""
        if not log_path.is_file():
            return {"available": False, "log_path": str(log_path), "refusals": [], "total": 0}
        all_refusals = read_refusals(log_path)
        shown = all_refusals[-limit:]
        return {
            "available": True,
            "log_path": str(log_path),
            "total": len(all_refusals),
            "truncated": len(shown) < len(all_refusals),
            "refusals": [r.model_dump(mode="json") for r in shown],
        }

    if allow_writes:

        def _write_graph() -> Graph:
            """Open the graph for writing for the length of one request.

            `Graph.open()` takes a non-blocking exclusive `flock`. If an agent
            run holds it, that raises `SingleWriterViolation`, which becomes a
            409 rather than a 500: the researcher is told a run is in progress
            and can retry, which is true and actionable. Deliberately no
            retry loop and no lock timeout — a UI that silently waited on the
            lock would make the single-writer rule feel like a bug instead of
            a design commitment."""
            try:
                return Graph.open(db_path, log_path)
            except SingleWriterViolation as e:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"{e} — an agent run is writing to this graph right now. "
                        "Nothing was changed; try again when it finishes."
                    ),
                ) from e
            except FileNotFoundError as e:
                raise HTTPException(status_code=503, detail=str(e)) from e

        def _verdict(node_id: str, action: str, reason: str | None) -> dict[str, Any]:
            graph = _write_graph()
            try:
                try:
                    method = {
                        "accept": graph.accept, "reject": graph.reject, "reopen": graph.reopen,
                    }[action]
                    kwargs: dict[str, Any] = {"authored_by": RESEARCHER}
                    if action in ("reject", "reopen"):
                        kwargs["reason"] = reason
                    decision_id = method(node_id, **kwargs)
                except NodeNotFound as e:
                    raise HTTPException(status_code=404, detail=str(e)) from e
                except CohortError as e:
                    # A refused write, already recorded to the log by
                    # `graph._refuse()`. 422: the request was well formed but
                    # the graph's own rules declined it — which is a real
                    # answer from this system, not a server fault.
                    raise HTTPException(
                        status_code=422,
                        detail={"rule": type(e).__name__, "message": str(e)},
                    ) from e
                node = graph.get_node(node_id)
                return {
                    "node": _node_json(graph, node),
                    "decision_node_id": decision_id,
                }
            finally:
                graph.close()

        @app.post("/api/accept")
        def accept(
            id: str = Query(..., min_length=1),
            body: dict[str, Any] = Body(default={}),
        ) -> dict[str, Any]:
            """Promote a node to `accepted` as the researcher.

            Query parameter for the id, same reason as `/api/node`: passage
            ids contain `#`."""
            return _verdict(id, "accept", None)

        @app.post("/api/reject")
        def reject(
            id: str = Query(..., min_length=1),
            body: dict[str, Any] = Body(default={}),
        ) -> dict[str, Any]:
            """Reject a node, with a reason.

            The reason is required by the graph, not by this layer
            (`MissingRejectionReason`) — passing it through and letting the
            write boundary refuse keeps one rule in one place, and the refusal
            gets logged like any other."""
            return _verdict(id, "reject", (body or {}).get("reason"))

        @app.post("/api/reopen")
        def reopen(
            id: str = Query(..., min_length=1),
            body: dict[str, Any] = Body(default={}),
        ) -> dict[str, Any]:
            """Reopen a rejected node. A researcher action by design: DESIGN.md
            §8 says rejection persists and "reopening is a researcher
            action"."""
            return _verdict(id, "reopen", (body or {}).get("reason"))

    if FRONTEND_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "index.html")

    return app
