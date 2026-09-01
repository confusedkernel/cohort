"""Read-only JSON API over the evidence graph (build order stage 5).

**Read-only is a design position, not a phase.** Every endpoint here opens the
projection through `Graph.open_read_only()`, which takes no writer lock, so
the API can serve while an agent run is writing — and cannot itself write,
because SQLite is opened `mode=ro` and no `EventLog` is attached. The
researcher's accept/reject (DESIGN.md §13 stage 5) is deliberately *not* here:
those are writes, and a writing UI would have to hold the exclusive lock for
as long as a browser tab is open, which would stop every agent run in the
meantime. That concurrency question deserves its own decision rather than
being settled by whichever endpoint got written first.

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

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..errors import NodeNotFound
from ..graph import Graph
from ..schemas import EdgeType, NodeType

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
        "authorship": [a.model_dump(mode="json") for a in edge.authorship],
        "created_seq": edge.created_seq,
    }


def create_app(db_path: str | Path) -> FastAPI:
    """Build the app around one projection path.

    A fresh read-only `Graph` is opened per request rather than held open for
    the app's lifetime. That is deliberate: an agent run writing to the same
    file advances it constantly, and a long-lived connection would serve a
    snapshot that silently ages. It also keeps sqlite3's same-thread rule
    satisfied without pinning the server to one worker."""
    db_path = Path(db_path)
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
            return {"ok": True, "db_path": str(db_path), "nodes": counts, "edges": edges}
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

    if FRONTEND_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "index.html")

    return app
