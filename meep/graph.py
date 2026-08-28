"""SQLite projection — the only writer (design doc §5 principles 4 and 7).

The graph is rebuildable from the event log; if the two disagree, the log is
right and the projection has a bug (principle 1). Every public write-boundary
method here follows the same shape: validate against current state, log the
event, then apply it — `_apply()` is the only place SQL runs, is reused
verbatim by `rebuild()`'s shadow graph, and never generates a random id or a
fresh timestamp, so replay is deterministic.
"""
from __future__ import annotations

import fcntl
import itertools
import json
import sqlite3
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import NoReturn

from .errors import (
    EdgeDomainViolation,
    EdgeEndpointMissing,
    EdgeSelfLoop,
    MeepError,
    MissingRejectionReason,
    NodeNotFound,
    NoEventLog,
    NotResearcher,
    PassageNotLocated,
    PersistentRejection,
    RebuildMismatch,
    RungSkipped,
    SingleWriterViolation,
    UnattestableClaim,
    UnattestableConjecture,
)
from .eventlog import EventLog, read_events
from .schemas import (
    RESEARCHER,
    Authorship,
    ClaimPayload,
    ConjecturePayload,
    DecisionPayload,
    Edge,
    EdgeType,
    Event,
    IndependentSupport,
    Node,
    NodeStatus,
    NodeType,
    PassagePayload,
    QueryPayload,
    RebuildReport,
    WitnessPayload,
)

#: design doc §6's edge table. "any" = any (type, type) pair is legal;
#: "same_type" = src.type == dst.type, any type.
EDGE_DOMAINS: dict[EdgeType, set[tuple[NodeType, NodeType]] | str] = {
    EdgeType.ATTESTS: {
        (NodeType.PASSAGE, NodeType.CLAIM),
        (NodeType.PASSAGE, NodeType.CONJECTURE),
    },
    EdgeType.CONTRADICTS: "any",
    EdgeType.PARALLEL_OF: {
        (NodeType.PASSAGE, NodeType.PASSAGE),
        (NodeType.WITNESS, NodeType.WITNESS),
    },
    EdgeType.DESCENDS_FROM: {
        (NodeType.PASSAGE, NodeType.PASSAGE),
        (NodeType.WITNESS, NodeType.WITNESS),
    },
    EdgeType.QUOTES: {(NodeType.PASSAGE, NodeType.PASSAGE)},
    EdgeType.TESTS: {(NodeType.QUERY, NodeType.CONJECTURE)},
    EdgeType.SUPERSEDES: "same_type",
    EdgeType.PART_OF: {(NodeType.PASSAGE, NodeType.WITNESS)},
}

#: written as two rows (both directions) from one logged event, so a
#: contradiction or a shared-transmission relation is never missed just
#: because a query only checked one direction (design doc §11's "not
#: symmetric on read" weak point, fixed by construction here).
SYMMETRIC_EDGE_TYPES = {EdgeType.CONTRADICTS, EdgeType.PARALLEL_OF}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'proposed',
    payload         TEXT NOT NULL,
    rejected_reason TEXT,
    created_seq     INTEGER NOT NULL,
    updated_seq     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);

CREATE TABLE IF NOT EXISTS node_authorship (
    node_id TEXT NOT NULL,
    author  TEXT NOT NULL,
    action  TEXT NOT NULL,
    at      TEXT NOT NULL,
    seq     INTEGER NOT NULL,
    PRIMARY KEY (node_id, seq)
);

CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    src         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    created_seq INTEGER NOT NULL,
    UNIQUE(type, src, dst)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(type, src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(type, dst);

CREATE TABLE IF NOT EXISTS edge_authorship (
    edge_id TEXT NOT NULL,
    author  TEXT NOT NULL,
    action  TEXT NOT NULL,
    at      TEXT NOT NULL,
    seq     INTEGER NOT NULL,
    PRIMARY KEY (edge_id, seq)
);
"""


class Graph:
    def __init__(self, db_path: str | Path, event_log: EventLog | None = None) -> None:
        self.db_path = db_path
        self.event_log = event_log
        self._lock_file = None
        self._in_memory = str(db_path) == ":memory:"
        if not self._in_memory:
            self._acquire_lock(Path(db_path))
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    @classmethod
    def open(cls, db_path: str | Path, log_path: str | Path) -> "Graph":
        db_path = Path(db_path)
        log_path = Path(log_path)
        fresh_db = not db_path.exists()
        event_log = EventLog(log_path)
        graph = cls(db_path, event_log=event_log)
        if fresh_db and len(event_log) > 0:
            for ev in read_events(log_path):
                graph._apply(ev)
        return graph

    # --- lifecycle -------------------------------------------------------

    def _acquire_lock(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = db_path.with_suffix(db_path.suffix + ".lock")
        f = open(lock_path, "w")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.close()
            raise SingleWriterViolation(
                f"another process already holds the write lock on {db_path}"
            )
        self._lock_file = f

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
        if self._lock_file is not None:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None

    def __enter__(self) -> "Graph":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def event_log_or_raise(self) -> EventLog:
        if self.event_log is None:
            raise NoEventLog("this Graph has no attached EventLog; writes are disabled")
        return self.event_log

    # --- proposal ----------------------------------------------------------

    def propose_witness(self, payload: WitnessPayload, *, authored_by: str) -> str:
        return self._propose_source_derived(NodeType.WITNESS, payload, authored_by=authored_by)

    def propose_passage(
        self, payload: PassagePayload, *, witness_id: str, authored_by: str
    ) -> str:
        if self._get_row(witness_id) is None:
            self._refuse(
                "propose", authored_by,
                EdgeEndpointMissing(f"witness {witness_id} does not exist"),
                node_type=NodeType.PASSAGE,
            )
        node_id = f"{NodeType.PASSAGE}:{payload.canonical_ref}"
        existing = self._get_row(node_id)
        if existing is not None and existing["status"] == NodeStatus.REJECTED:
            self._refuse(
                "propose", authored_by, PersistentRejection(node_id),
                node_id=node_id, node_type=NodeType.PASSAGE,
            )
        edge_id = None if existing is not None else f"edge:{uuid.uuid4().hex}"
        ev = self.event_log_or_raise().append(
            "propose", authored_by=authored_by, node_id=node_id, node_type=NodeType.PASSAGE,
            edge_id=edge_id, edge_type=(EdgeType.PART_OF if edge_id else None),
            detail={
                "payload": payload.model_dump(mode="json"),
                "witness_id": witness_id,
                "converge": existing is not None,
            },
        )
        self._apply(ev)
        return node_id

    def propose_claim(self, payload: ClaimPayload, *, authored_by: str) -> str:
        return self._propose_agent_authored(NodeType.CLAIM, payload, authored_by=authored_by)

    def propose_conjecture(self, payload: ConjecturePayload, *, authored_by: str) -> str:
        return self._propose_agent_authored(NodeType.CONJECTURE, payload, authored_by=authored_by)

    def propose_query(self, payload: QueryPayload, *, authored_by: str) -> str:
        return self._propose_agent_authored(NodeType.QUERY, payload, authored_by=authored_by)

    def _propose_source_derived(self, node_type: NodeType, payload, *, authored_by: str) -> str:
        node_id = f"{node_type}:{payload.canonical_ref}"
        existing = self._get_row(node_id)
        if existing is not None and existing["status"] == NodeStatus.REJECTED:
            self._refuse(
                "propose", authored_by, PersistentRejection(node_id),
                node_id=node_id, node_type=node_type,
            )
        ev = self.event_log_or_raise().append(
            "propose", authored_by=authored_by, node_id=node_id, node_type=node_type,
            detail={
                "payload": payload.model_dump(mode="json"),
                "converge": existing is not None,
            },
        )
        self._apply(ev)
        return node_id

    def _propose_agent_authored(self, node_type: NodeType, payload, *, authored_by: str) -> str:
        node_id = f"{node_type}:{uuid.uuid4().hex}"
        ev = self.event_log_or_raise().append(
            "propose", authored_by=authored_by, node_id=node_id, node_type=node_type,
            detail={"payload": payload.model_dump(mode="json"), "converge": False},
        )
        self._apply(ev)
        return node_id

    # --- the ladder (design doc §8) -----------------------------------------

    def attest(self, node_id: str, *, authored_by: str) -> None:
        node = self._require_node(node_id)
        if node.status != NodeStatus.PROPOSED:
            self._refuse(
                "attest", authored_by,
                RungSkipped(f"{node_id} is {node.status}, not proposed"),
                node_id=node_id, node_type=node.type,
            )
        if node.type == NodeType.CLAIM:
            if not self._has_qualifying_attestation(node_id):
                self._refuse(
                    "attest", authored_by, UnattestableClaim(node_id),
                    node_id=node_id, node_type=node.type,
                )
        elif node.type == NodeType.CONJECTURE:
            if not self._has_inbound_edge(node_id, EdgeType.TESTS):
                self._refuse(
                    "attest", authored_by, UnattestableConjecture(node_id),
                    node_id=node_id, node_type=node.type,
                )
        elif node.type == NodeType.PASSAGE:
            if not self._has_outbound_edge(node_id, EdgeType.PART_OF):
                self._refuse(
                    "attest", authored_by, PassageNotLocated(node_id),
                    node_id=node_id, node_type=node.type,
                )
        ev = self.event_log_or_raise().append(
            "attest", authored_by=authored_by, node_id=node_id, node_type=node.type, detail={},
        )
        self._apply(ev)

    def accept(self, node_id: str, *, authored_by: str, reason: str | None = None) -> str:
        self._require_researcher(authored_by, action="accept", node_id=node_id)
        node = self._require_node(node_id)
        if node.status != NodeStatus.ATTESTED:
            self._refuse(
                "accept", authored_by,
                RungSkipped(f"{node_id} is {node.status}, not attested"),
                node_id=node_id, node_type=node.type,
            )
        return self._apply_verdict_write(node, "accept", authored_by, reason)

    def reject(self, node_id: str, *, authored_by: str, reason: str) -> str:
        self._require_researcher(authored_by, action="reject", node_id=node_id)
        if not reason or not reason.strip():
            self._refuse(
                "reject", authored_by, MissingRejectionReason(node_id), node_id=node_id,
            )
        node = self._require_node(node_id)
        if node.status not in (NodeStatus.PROPOSED, NodeStatus.ATTESTED):
            self._refuse(
                "reject", authored_by,
                RungSkipped(f"{node_id} is {node.status}, cannot reject"),
                node_id=node_id, node_type=node.type,
            )
        return self._apply_verdict_write(node, "reject", authored_by, reason)

    def reopen(self, node_id: str, *, authored_by: str, reason: str) -> str:
        self._require_researcher(authored_by, action="reopen", node_id=node_id)
        if not reason or not reason.strip():
            self._refuse(
                "reopen", authored_by, MissingRejectionReason(node_id), node_id=node_id,
            )
        node = self._require_node(node_id)
        if node.status != NodeStatus.REJECTED:
            self._refuse(
                "reopen", authored_by,
                RungSkipped(f"{node_id} is {node.status}, not rejected"),
                node_id=node_id, node_type=node.type,
            )
        return self._apply_verdict_write(node, "reopen", authored_by, reason)

    def _apply_verdict_write(self, node: Node, event: str, authored_by: str, reason: str | None) -> str:
        decision_id = f"{NodeType.DECISION}:{uuid.uuid4().hex}"
        clean_reason = reason.strip() if reason and reason.strip() else None
        ev = self.event_log_or_raise().append(
            event, authored_by=authored_by, node_id=node.id, node_type=node.type,
            detail={"decision_node_id": decision_id, "reason": clean_reason},
        )
        self._apply(ev)
        return decision_id

    # --- edges (design doc §6) ----------------------------------------------

    def add_edge(self, edge_type: EdgeType, src: str, dst: str, *, authored_by: str) -> str:
        if src == dst:
            self._refuse(
                "add_edge", authored_by, EdgeSelfLoop(f"{src} -> {dst}"), edge_type=edge_type,
            )
        src_row = self._get_row(src)
        dst_row = self._get_row(dst)
        if src_row is None:
            self._refuse(
                "add_edge", authored_by,
                EdgeEndpointMissing(f"src {src} does not exist"), edge_type=edge_type,
            )
        if dst_row is None:
            self._refuse(
                "add_edge", authored_by,
                EdgeEndpointMissing(f"dst {dst} does not exist"), edge_type=edge_type,
            )
        domain = EDGE_DOMAINS[edge_type]
        if domain != "any":
            if domain == "same_type":
                ok = src_row["type"] == dst_row["type"]
            else:
                ok = (src_row["type"], dst_row["type"]) in domain
            if not ok:
                self._refuse(
                    "add_edge", authored_by,
                    EdgeDomainViolation(
                        f"{edge_type} not valid from {src_row['type']} to {dst_row['type']}"
                    ),
                    edge_type=edge_type,
                )
        existing = self.conn.execute(
            "SELECT id FROM edges WHERE type=? AND src=? AND dst=?", (edge_type, src, dst)
        ).fetchone()
        edge_id = existing["id"] if existing else f"edge:{uuid.uuid4().hex}"
        ev = self.event_log_or_raise().append(
            "add_edge", authored_by=authored_by, edge_id=edge_id, edge_type=edge_type,
            detail={"src": src, "dst": dst, "converge": existing is not None},
        )
        self._apply(ev)
        return edge_id

    def edges(
        self, *, edge_type: EdgeType | None = None, src: str | None = None, dst: str | None = None
    ) -> list[Edge]:
        query = "SELECT * FROM edges WHERE 1=1"
        params: list = []
        if edge_type is not None:
            query += " AND type=?"
            params.append(edge_type)
        if src is not None:
            query += " AND src=?"
            params.append(src)
        if dst is not None:
            query += " AND dst=?"
            params.append(dst)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_edge(r) for r in rows]

    # --- read-only surface ---------------------------------------------------

    def get_node(self, node_id: str) -> Node:
        return self._require_node(node_id)

    def citable(self) -> list[Node]:
        """Only accepted, non-decision nodes — the only things usable as a
        premise or citable in output (design doc §5 principle 6). Decision
        nodes are always status=accepted (they bypass the ladder) but are
        audit bookkeeping, not evidence."""
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE status=? AND type!=?",
            (NodeStatus.ACCEPTED, NodeType.DECISION),
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def rejected(self, *, node_type: NodeType | None = None) -> list[Node]:
        """Rejected nodes, with their reasons (design doc §8: "the graph
        records the judgement calls, not only the findings"). For
        `witness`/`passage`, persistent rejection is already enforced
        mechanically at the write boundary via `canonical_ref` identity. For
        `claim`/`conjecture`, there is no content-derived identity to block
        on — principle 5 forbids hashing agent-produced text into identity —
        so a rejected conjecture cannot be caught by id if reworded. This
        method is how that gap gets closed instead: by making rejections
        visible to an agent's own reasoning, not by faking an identity key
        for content the design deliberately declines to hash."""
        query = "SELECT * FROM nodes WHERE status=?"
        params: list = [NodeStatus.REJECTED]
        if node_type is not None:
            query += " AND type=?"
            params.append(node_type)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_node(r) for r in rows]

    def independent_support(self, node_id: str) -> IndependentSupport:
        """design doc §4, §11 — the counter-argument to consensus-seeking:
        attesting count stays put while `independent` flips to False the
        instant a descent/parallel relation links two supporting witnesses."""
        self._require_node(node_id)
        attesting = self.conn.execute(
            "SELECT src FROM edges WHERE type=? AND dst=?", (EdgeType.ATTESTS, node_id)
        ).fetchall()
        passages = [r["src"] for r in attesting]
        witnesses: dict[str, str | None] = {}
        for p in passages:
            row = self.conn.execute(
                "SELECT dst FROM edges WHERE type=? AND src=?", (EdgeType.PART_OF, p)
            ).fetchone()
            witnesses[p] = row["dst"] if row else None
        distinct_witnesses = {w for w in witnesses.values() if w is not None}
        subjects = list(dict.fromkeys([*passages, *distinct_witnesses]))
        flips = [
            (a, b) for a, b in itertools.combinations(subjects, 2)
            if self._related(a, b, (EdgeType.DESCENDS_FROM, EdgeType.PARALLEL_OF))
        ]
        return IndependentSupport(
            node_id=node_id,
            attesting_count=len(passages),
            distinct_witnesses=len(distinct_witnesses),
            independent=not flips,
            non_independent_pairs=flips,
        )

    def rebuild(self) -> RebuildReport:
        """Replay the event log into a shadow graph and diff it against the
        live projection. A failing diff is a bug, not a warning (design doc
        §5 principle 1)."""
        log_path = self.event_log_or_raise().path
        shadow = Graph(":memory:", event_log=None)
        events = list(read_events(log_path))
        for ev in events:
            shadow._apply(ev)
        diff = self._diff(shadow)
        shadow.close()
        if diff:
            raise RebuildMismatch(diff)
        return RebuildReport(
            ok=True, events_replayed=len(events),
            nodes=self._count("nodes"), edges=self._count("edges"),
        )

    # --- apply: the only place SQL runs (used live and by rebuild) -----------

    def _apply(self, ev: Event) -> None:
        if ev.event == "propose":
            self._apply_propose(ev)
        elif ev.event == "attest":
            self._apply_attest(ev)
        elif ev.event == "accept":
            self._apply_verdict(ev, NodeStatus.ACCEPTED, "accepted")
        elif ev.event == "reject":
            self._apply_verdict(ev, NodeStatus.REJECTED, "rejected")
        elif ev.event == "reopen":
            self._apply_verdict(ev, NodeStatus.PROPOSED, "reopened")
        elif ev.event == "add_edge":
            self._apply_add_edge(ev)
        elif ev.event == "refused":
            pass  # an audit marker only; never mutates state
        else:  # pragma: no cover — Event already validates against EVENT_TYPES
            raise MeepError(f"no _apply handler for event {ev.event!r}")

    def _apply_propose(self, ev: Event) -> None:
        detail = ev.detail
        existing = self._get_row(ev.node_id)
        if existing is not None:
            self._add_authorship("node", ev.node_id, ev.authored_by, "converged", ev.at, ev.seq)
            self.conn.execute("UPDATE nodes SET updated_seq=? WHERE id=?", (ev.seq, ev.node_id))
        else:
            self.conn.execute(
                "INSERT INTO nodes (id, type, status, payload, rejected_reason, "
                "created_seq, updated_seq) VALUES (?, ?, ?, ?, NULL, ?, ?)",
                (
                    ev.node_id, ev.node_type, NodeStatus.PROPOSED,
                    json.dumps(detail["payload"]), ev.seq, ev.seq,
                ),
            )
            self._add_authorship("node", ev.node_id, ev.authored_by, "proposed", ev.at, ev.seq)
        if ev.edge_id is not None and ev.edge_type is not None:
            self._insert_edge_row(ev.edge_id, ev.edge_type, ev.node_id, detail["witness_id"], ev.seq)
            self._add_authorship("edge", ev.edge_id, ev.authored_by, "proposed", ev.at, ev.seq)
        self.conn.commit()

    def _apply_attest(self, ev: Event) -> None:
        self.conn.execute(
            "UPDATE nodes SET status=?, updated_seq=? WHERE id=?",
            (NodeStatus.ATTESTED, ev.seq, ev.node_id),
        )
        self._add_authorship("node", ev.node_id, ev.authored_by, "attested", ev.at, ev.seq)
        self.conn.commit()

    def _apply_verdict(self, ev: Event, new_status: NodeStatus, verdict: str) -> None:
        detail = ev.detail
        decision_id = detail["decision_node_id"]
        reason = detail.get("reason")
        rejected_reason = reason if new_status == NodeStatus.REJECTED else None
        self.conn.execute(
            "UPDATE nodes SET status=?, rejected_reason=?, updated_seq=? WHERE id=?",
            (new_status, rejected_reason, ev.seq, ev.node_id),
        )
        self._add_authorship("node", ev.node_id, ev.authored_by, verdict, ev.at, ev.seq)
        decision_payload = DecisionPayload(
            subject_node_id=ev.node_id, verdict=verdict, reason=reason
        ).model_dump(mode="json")
        self.conn.execute(
            "INSERT INTO nodes (id, type, status, payload, rejected_reason, "
            "created_seq, updated_seq) VALUES (?, ?, 'accepted', ?, NULL, ?, ?)",
            (decision_id, NodeType.DECISION, json.dumps(decision_payload), ev.seq, ev.seq),
        )
        self._add_authorship("node", decision_id, ev.authored_by, "proposed", ev.at, ev.seq)
        self.conn.commit()

    def _apply_add_edge(self, ev: Event) -> None:
        src, dst = ev.detail["src"], ev.detail["dst"]
        if ev.detail.get("converge"):
            self._add_authorship("edge", ev.edge_id, ev.authored_by, "converged", ev.at, ev.seq)
            self.conn.commit()
            return
        self._insert_edge_row(ev.edge_id, ev.edge_type, src, dst, ev.seq)
        self._add_authorship("edge", ev.edge_id, ev.authored_by, "proposed", ev.at, ev.seq)
        if ev.edge_type in SYMMETRIC_EDGE_TYPES:
            rev_id = f"{ev.edge_id}:rev"
            self._insert_edge_row(rev_id, ev.edge_type, dst, src, ev.seq)
            self._add_authorship("edge", rev_id, ev.authored_by, "proposed", ev.at, ev.seq)
        self.conn.commit()

    # --- small helpers ---------------------------------------------------------

    def _refuse(
        self, attempted: str, authored_by: str, error: MeepError, *,
        node_id: str | None = None, edge_id: str | None = None,
        node_type: NodeType | None = None, edge_type: EdgeType | None = None,
    ) -> NoReturn:
        if self.event_log is not None:
            self.event_log.append(
                "refused", authored_by=authored_by, node_id=node_id, edge_id=edge_id,
                node_type=node_type, edge_type=edge_type,
                detail={"attempted": attempted, "rule": type(error).__name__, "message": str(error)},
            )
        raise error

    def _require_researcher(self, authored_by: str, *, action: str, node_id: str | None = None) -> None:
        if authored_by != RESEARCHER:
            self._refuse(
                action, authored_by,
                NotResearcher(f"{action} requires authored_by='researcher', got {authored_by!r}"),
                node_id=node_id,
            )

    def _require_node(self, node_id: str) -> Node:
        row = self._get_row(node_id)
        if row is None:
            raise NodeNotFound(node_id)
        return self._row_to_node(row)

    def _get_row(self, node_id: str):
        return self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()

    def _has_qualifying_attestation(self, node_id: str) -> bool:
        rows = self.conn.execute(
            "SELECT n.status FROM edges e JOIN nodes n ON n.id = e.src "
            "WHERE e.type=? AND e.dst=?",
            (EdgeType.ATTESTS, node_id),
        ).fetchall()
        return any(r["status"] in (NodeStatus.ATTESTED, NodeStatus.ACCEPTED) for r in rows)

    def _has_inbound_edge(self, node_id: str, edge_type: EdgeType) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM edges WHERE type=? AND dst=? LIMIT 1", (edge_type, node_id)
        ).fetchone()
        return row is not None

    def _has_outbound_edge(self, node_id: str, edge_type: EdgeType) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM edges WHERE type=? AND src=? LIMIT 1", (edge_type, node_id)
        ).fetchone()
        return row is not None

    def _related(self, a: str, b: str, edge_types: Iterable[EdgeType]) -> bool:
        types = tuple(edge_types)
        placeholders = ",".join("?" for _ in types)
        row = self.conn.execute(
            f"SELECT 1 FROM edges WHERE type IN ({placeholders}) AND "
            f"((src=? AND dst=?) OR (src=? AND dst=?)) LIMIT 1",
            (*types, a, b, b, a),
        ).fetchone()
        return row is not None

    def _insert_edge_row(self, edge_id: str, edge_type: EdgeType, src: str, dst: str, seq: int) -> None:
        self.conn.execute(
            "INSERT INTO edges (id, type, src, dst, created_seq) VALUES (?, ?, ?, ?, ?)",
            (edge_id, edge_type, src, dst, seq),
        )

    def _add_authorship(self, kind: str, id_: str, author: str, action: str, at: str, seq: int) -> None:
        table = "node_authorship" if kind == "node" else "edge_authorship"
        col = "node_id" if kind == "node" else "edge_id"
        self.conn.execute(
            f"INSERT INTO {table} ({col}, author, action, at, seq) VALUES (?, ?, ?, ?, ?)",
            (id_, author, action, at, seq),
        )

    def _row_to_node(self, row) -> Node:
        authorship = [
            Authorship(author=r["author"], at=r["at"], action=r["action"])
            for r in self.conn.execute(
                "SELECT author, action, at FROM node_authorship WHERE node_id=? ORDER BY seq",
                (row["id"],),
            ).fetchall()
        ]
        return Node(
            id=row["id"], type=row["type"], status=row["status"],
            payload=json.loads(row["payload"]), authorship=authorship,
            rejected_reason=row["rejected_reason"],
            created_seq=row["created_seq"], updated_seq=row["updated_seq"],
        )

    def _row_to_edge(self, row) -> Edge:
        authorship = [
            Authorship(author=r["author"], at=r["at"], action=r["action"])
            for r in self.conn.execute(
                "SELECT author, action, at FROM edge_authorship WHERE edge_id=? ORDER BY seq",
                (row["id"],),
            ).fetchall()
        ]
        return Edge(
            id=row["id"], type=row["type"], src=row["src"], dst=row["dst"],
            authorship=authorship, created_seq=row["created_seq"],
        )

    def _count(self, table: str) -> int:
        return self.conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]

    def _diff(self, other: "Graph") -> dict:
        mine, theirs = self._snapshot(), other._snapshot()
        return {} if mine == theirs else {"self": mine, "other": theirs}

    def _snapshot(self) -> dict:
        nodes = {
            r["id"]: (r["type"], r["status"], r["payload"], r["rejected_reason"])
            for r in self.conn.execute("SELECT * FROM nodes").fetchall()
        }
        edges = {
            r["id"]: (r["type"], r["src"], r["dst"])
            for r in self.conn.execute("SELECT * FROM edges").fetchall()
        }
        node_auth = sorted(
            (r["node_id"], r["author"], r["action"], r["seq"])
            for r in self.conn.execute("SELECT * FROM node_authorship").fetchall()
        )
        edge_auth = sorted(
            (r["edge_id"], r["author"], r["action"], r["seq"])
            for r in self.conn.execute("SELECT * FROM edge_authorship").fetchall()
        )
        return {"nodes": nodes, "edges": edges, "node_auth": node_auth, "edge_auth": edge_auth}
