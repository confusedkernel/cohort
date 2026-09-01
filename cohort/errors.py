"""One exception per rule the design claims (design doc §0).

Pydantic owns *shape* validity (a malformed payload, a `basis` that isn't a
sentence) — those raise `pydantic.ValidationError` at construction, before a
write ever reaches the graph. This module owns *state* validity — rules that
depend on what's already in the graph, raised by `graph.py`'s write
boundary and nowhere else.
"""
from __future__ import annotations


class CohortError(Exception):
    """Base for every COHORT rule violation."""


# --- event log ---------------------------------------------------------------

class UnknownEventType(CohortError):
    """An event string outside the closed vocabulary."""


class NoEventLog(CohortError):
    """A write was attempted on a Graph with no attached EventLog."""


# --- rebuild (design doc §5 principle 1) --------------------------------------

class RebuildMismatch(CohortError):
    """The event log, replayed, does not match the live projection."""


# --- edges (design doc §6) ----------------------------------------------------

class EdgeDomainViolation(CohortError):
    """This edge type is not valid between these two node types."""


class EdgeEndpointMissing(CohortError):
    """An edge's src or dst node id does not exist."""


class EdgeSelfLoop(CohortError):
    """An edge's src and dst are the same node."""


# --- the falsifiability gate (design doc §7) ----------------------------------

class UnattestableClaim(CohortError):
    """A claim has no attests edge from an attested-or-better passage."""


class UnattestableConjecture(CohortError):
    """A conjecture has no tests edge; attests edges never satisfy this."""


class PassageNotLocated(CohortError):
    """A passage has no part_of edge to a witness."""


# --- the promotion ladder (design doc §8) -------------------------------------

class RungSkipped(CohortError):
    """A status transition was attempted out of order."""


class NotResearcher(CohortError):
    """Only the researcher may accept, reject, or reopen a node."""


class MissingRejectionReason(CohortError):
    """reject()/reopen() requires a stated reason."""


class PersistentRejection(CohortError):
    """A rejected node cannot be re-proposed; only the researcher may reopen it."""


# --- lookup --------------------------------------------------------------------

class EdgeNotFound(CohortError):
    """No such edge id. Same discipline as `NodeNotFound`: an id that does not
    resolve is refused rather than silently ignored."""


class PersistentRetraction(CohortError):
    """A retracted edge may not be redrawn by the next worker along.

    The mirror of `PersistentRejection` for edges, and for the same reason
    (design doc §8): without it, retracting a wrong `parallel_of` would last
    only until the next `link_parallels` run put it back, and the researcher's
    judgement would be quietly overwritten by a tool. Restoring one is a
    researcher action.
    """


class EdgeAlreadyRetracted(CohortError):
    """Retracting a retracted edge, or restoring one that is not retracted."""


class NodeNotFound(CohortError):
    """No node with this id exists."""


# --- single writer (design doc §5 principle 7) --------------------------------

class SingleWriterViolation(CohortError):
    """Another process already holds the write lock on this graph."""
