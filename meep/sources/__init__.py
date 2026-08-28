"""The source interface (design doc §2): search(query) / fetch(ref), and
nothing more. Governance — licensing, allowlists, retention — is ATELIER's
job, not this phase's; this package only reads text."""
from __future__ import annotations

from .base import SearchHit, Source, SourceRecord

__all__ = ["SearchHit", "Source", "SourceRecord"]
