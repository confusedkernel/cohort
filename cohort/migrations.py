"""Forward-only schema migrations for the SQLite projection.

Uses SQLite's own `PRAGMA user_version` (an integer stored in the database
file's header) rather than a hand-built tracking table — SQLite already
provides exactly the primitive this needs. No checksums, no advisory locks:
those solve a problem COHORT doesn't have (many independently-deployed
instances verifying they're applying identically-named migrations
consistently). COHORT is one local tool, one writer at a time — `Graph`'s
`fcntl.flock` (acquired before this ever runs) already serializes schema
changes, and migrations are reviewed the ordinary way through git, not
independently re-verified at runtime.

`PRAGMA user_version` behaves identically on `:memory:` connections, so
`Graph.rebuild()`'s shadow graph applies the same migrations through the
same `Graph.__init__` path with no special-casing.
"""
from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass


class MigrationError(Exception):
    """A migration was registered or applied out of order."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str
    backfill: Callable[[sqlite3.Connection], None] | None = None


_SCHEMA_V1 = """
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

-- Sidecar identity, not a graph node (see AgentProfile's docstring).
-- authored_by is NOT enforced as a foreign key against this table: an agent
-- may write before registering, and every ad hoc authored_by string that
-- predates this table keeps working unregistered.
CREATE TABLE IF NOT EXISTS agents (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    corpus_scope TEXT,
    method_label TEXT,
    created_seq  INTEGER NOT NULL
);
"""

def _backfill_payload_hashes(conn: sqlite3.Connection) -> None:
    """Every pre-existing row gets hashed from its already-stored `payload`
    bytes, so `Graph.verify_integrity()` never needs a third "predates
    hashing" bucket — every row ends up hashed uniformly. Backfilled rows
    just can't detect tampering that happened before this column existed,
    which is inherent, not a gap."""
    rows = conn.execute("SELECT id, payload FROM nodes").fetchall()
    for node_id, payload in rows:
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        conn.execute("UPDATE nodes SET payload_hash=? WHERE id=?", (digest, node_id))


MIGRATIONS: list[Migration] = [
    Migration(1, "baseline", _SCHEMA_V1),
    Migration(
        2, "node_payload_hash",
        "ALTER TABLE nodes ADD COLUMN payload_hash TEXT;",
        backfill=_backfill_payload_hashes,
    ),
    #: Why an edge needs a reason: `contradicts` is the only edge type whose
    #: domain is "any", so the write boundary can check almost nothing about
    #: it, while the UI renders it as prominently as evidence. "Disagreement
    #: made visible" (DESIGN.md §6) has to mean the *grounds* are visible
    #: too, not just the line. No backfill: edges written before this
    #: carried no reason, and inventing one would be fabrication.
    Migration(3, "edge_reason", "ALTER TABLE edges ADD COLUMN reason TEXT;"),
]

#: The `user_version` a fully-migrated projection carries. Derived from
#: `MIGRATIONS` rather than written out, so it cannot drift from the list it
#: describes. A reader that cannot migrate (`Graph.open_read_only`) compares
#: against this before trusting the columns it is about to select.
SCHEMA_VERSION = max(m.version for m in MIGRATIONS)


def apply_migrations(conn: sqlite3.Connection, migrations: list[Migration] = MIGRATIONS) -> None:
    """Apply every migration newer than the database's current
    `user_version`, in order, refusing anything out of sequence."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for m in sorted(migrations, key=lambda m: m.version):
        if m.version <= current:
            continue
        if m.version != current + 1:
            raise MigrationError(
                f"migration {m.version} ({m.name!r}) is not the next version "
                f"after {current}; migrations must apply forward, one at a time"
            )
        conn.executescript(m.sql)
        if m.backfill is not None:
            m.backfill(conn)
        conn.execute(f"PRAGMA user_version = {m.version}")
        current = m.version
    conn.commit()
