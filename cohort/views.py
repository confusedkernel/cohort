"""Shared read-shapes for the front ends.

The CLI and the web API must describe the same node the same way. When each had
its own serializer they drifted immediately — one returned the node flat, the
other nested it under a `node` key — so `cohort node X --json` and
`GET /api/node?id=X` disagreed about a graph they both read correctly.

These functions are the single answer. Nothing here imports FastAPI, so the
terminal front end does not drag in the optional `ui` extra to describe a node.
"""
from __future__ import annotations

from typing import Any

from .graph import Graph
from .schemas import EdgeType, NodeType

#: The two edge types that *discount* support rather than adding it: witnesses
#: linked by either are evidence of shared descent, not independent
#: confirmation. Named once so no front end has to re-derive it, and so none
#: can quietly omit the distinction docs/design.md §10 requires.
DISCOUNTING_EDGE_TYPES = frozenset({EdgeType.DESCENDS_FROM, EdgeType.PARALLEL_OF})


def node_json(graph: Graph, node) -> dict[str, Any]:
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


def edge_json(edge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "type": edge.type,
        "src": edge.src,
        "dst": edge.dst,
        "discounts": edge.type in DISCOUNTING_EDGE_TYPES,
        "reason": edge.reason,
        # A retracted edge is reported, not omitted: "the researcher withdrew
        # this" and "this was never asserted" are different facts, and only one
        # of them is worth showing.
        "retracted": edge.retracted_at is not None,
        "retracted_at": edge.retracted_at,
        "retracted_reason": edge.retracted_reason,
        "authorship": [a.model_dump(mode="json") for a in edge.authorship],
        "created_seq": edge.created_seq,
    }


def node_detail_json(graph: Graph, node_id: str) -> dict[str, Any]:
    """Everything provenance-on-click needs: the node, its verifications, its
    edges both ways, and — for a claim or conjecture — whether its support is
    independent.

    `independent_support` is present only where it means something. Reporting
    it for a witness would invite reading a bare `attesting_count` as a
    confidence number, which is the habit this system exists to break.
    """
    node = graph.get_node(node_id)
    detail = node_json(graph, node)
    detail["verifications"] = [node_json(graph, v) for v in graph.verifications(node_id)]
    # Include retracted edges here — the inspector is where the record is read,
    # and a withdrawal with its reason is part of the provenance.
    detail["edges_out"] = [edge_json(e) for e in graph.edges(src=node_id, include_retracted=True)]
    detail["edges_in"] = [edge_json(e) for e in graph.edges(dst=node_id, include_retracted=True)]
    if node.type in (NodeType.CLAIM, NodeType.CONJECTURE):
        detail["independent_support"] = graph.independent_support(node_id).model_dump(
            mode="json"
        )
    return detail
