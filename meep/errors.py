"""One exception per rule the design claims (design doc §0).

Pydantic owns *shape* validity (a malformed payload, a `basis` that isn't a
sentence) — those raise `pydantic.ValidationError` at construction, before a
write ever reaches the graph. This module owns *state* validity — rules that
depend on what's already in the graph, raised by `graph.py`'s write
boundary and nowhere else.
"""
from __future__ import annotations


class MeepError(Exception):
    """Base for every MEEP rule violation."""


# --- event log ---------------------------------------------------------------

class UnknownEventType(MeepError):
    """An event string outside the closed vocabulary."""


class NoEventLog(MeepError):
    """A write was attempted on a Graph with no attached EventLog."""


# --- rebuild (design doc §5 principle 1) --------------------------------------

class RebuildMismatch(MeepError):
    """The event log, replayed, does not match the live projection."""


# --- edges (design doc §6) ----------------------------------------------------

class EdgeDomainViolation(MeepError):
    """This edge type is not valid between these two node types."""


class EdgeEndpointMissing(MeepError):
    """An edge's src or dst node id does not exist."""


class EdgeSelfLoop(MeepError):
    """An edge's src and dst are the same node."""


# --- the falsifiability gate (design doc §7) ----------------------------------

class UnattestableClaim(MeepError):
    """A claim has no attests edge from an attested-or-better passage."""


class UnattestableConjecture(MeepError):
    """A conjecture has no tests edge; attests edges never satisfy this."""


class PassageNotLocated(MeepError):
    """A passage has no part_of edge to a witness."""


# --- the promotion ladder (design doc §8) -------------------------------------

class RungSkipped(MeepError):
    """A status transition was attempted out of order."""


class NotResearcher(MeepError):
    """Only the researcher may accept, reject, or reopen a node."""


class MissingRejectionReason(MeepError):
    """reject()/reopen() requires a stated reason."""


class PersistentRejection(MeepError):
    """A rejected node cannot be re-proposed; only the researcher may reopen it."""


# --- lookup --------------------------------------------------------------------

class NodeNotFound(MeepError):
    """No node with this id exists."""


# --- single writer (design doc §5 principle 7) --------------------------------

class SingleWriterViolation(MeepError):
    """Another process already holds the write lock on this graph."""
