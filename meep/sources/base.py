"""The source interface — shaped like ATELIER's adapter (design doc §2):
`search(query)` / `fetch(ref)`, and nothing more. No policy file, no
allowlist, no caps, no retention rules — that's ATELIER's job, staged for
integration later (design doc §6, build order stage 6), not reimplemented
here.

`max_results` is a plain function default, not a governance cap, so it's
added now (cheap, future-proofs the stage-6 adapter shape). `period` is
deliberately not added: it presumes a periodization/chronology scheme, and
design doc §14 lists chronology as an explicitly open decision. Adding it
later is additive; baking it in now would encode an unresolved choice.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchHit(_Model):
    ref: str
    title: str
    snippet: str | None = None


class SourceRecord(_Model):
    ref: str
    title: str
    text: str
    #: the canonical_ref this record's witness node should be identified by
    witness_ref: str = Field(min_length=1)
    locator: str | None = None
    note: str | None = None


class Source(ABC):
    #: short identifier for provenance, once ATELIER integration adds it
    source_name: str = "unknown"
    access_mode: str = "unknown"

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> list[SearchHit]: ...

    @abstractmethod
    def fetch(self, ref: str) -> SourceRecord: ...
