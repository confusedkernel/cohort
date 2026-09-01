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


class SelfAttestation(CohortError):
    """An agent tried to attest a claim or conjecture it authored.

    `attest` means "the mechanical preconditions hold", and the party with an
    interest in that answer is the worst party to give it. Both sibling
    projects separate the checker from the checked; this is that separation,
    enforced at the write boundary rather than asked for in a prompt.

    The researcher is exempt, deliberately. `accept` is already the human
    gate, the researcher is the accountable party, and requiring a second
    human would make single-researcher use impossible — which is not the
    problem this rule exists to solve.
    """


class ReviewerNotIndependent(CohortError):
    """The attesting agent shares a model family with an author of the node.

    A different agent id on the same model is not a different reader: it
    shares training priors and failure modes, so its confirmation is the
    author's own confirmation reported twice. That is the error
    `independent_support()` catches between witnesses, committed one layer up
    between readers — see `cohort.agents.roster`, which refuses the same
    overlap when a roster is assembled. This catches it at the write itself,
    where a roster check cannot reach: agents registered by separate runs
    still write to one graph.

    The family test is the same provider-prefix heuristic `roster` uses and
    inherits its limits. An agent whose model was never registered cannot be
    tested at all, and is allowed through: an unknown model is unknown, and
    refusing on it would state more than is known.
    """


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
