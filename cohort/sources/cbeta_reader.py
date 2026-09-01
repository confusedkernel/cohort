"""CBETA archive reader — COHORT's confirmed development corpus (docs/roadmap.md
"Scope revision"), locally-held but restrictively licensed (CC BY-NC-SA-
equivalent: non-commercial, attribution, share-alike, version and
intact-header requirements — not public domain).

A new module, not an extension of `local_reader.py`: CBETA is a single
hash-verified ZIP archive with TEI-header-skipping and span-location
concerns `LocalReader`'s manifest-driven plain-text-file model doesn't have.

The archive is configured by path (`CBETA_ARCHIVE_PATH`) and verified by
hash. Corpus bytes never enter this repository; this module is fully
exercised against a synthetic fixture (`tests/test_cbeta_reader.py`).

Witness identity is the bare CBETA canonical ref (`T02n0099`, `X10n0249`,
`J01nA042`), not an archive-version-qualified string — that's the text's
actual scholarly identity, stable across CBETA archive version bumps, unlike
an archive-internal path. The archive version and entry path are provenance
detail, carried in `SourceRecord.note` (which feeds `WitnessPayload.
source_terms`), not baked into the identity itself.

Identity spans all 24 collections, not Taisho alone: Taisho is under half the
archive's 20,190 entries, and restricting identity to it would make the
remainder unfetchable and unciteable. Taisho stays privileged in exactly one
place — `resolve_taisho_number()`, because `<cb:docNumber>` cross-references
are Taisho numbers.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

from .base import SearchHit, Source, SourceRecord

CBETA_ENTRY_PREFIX = "Bookcase/CBETA/XML/"
DEFAULT_MAX_ENTRY_BYTES = 50_000_000

#: Any CBETA canonical ref, across all 24 collections in v061 (T, X, J, A, B,
#: ZW, ...), not Taisho alone: only 8,982 of the archive's 20,190 entries are
#: Taisho, and a full-corpus index has to name the rest. Shape is
#: `{collection}{volume}n{number}`, where the number may carry a leading
#: letter (`J01nA042`, `B00na001`) or a trailing one (`ZW01n0014a`).
#:
#: The trailing letter is **part of the identity**, not noise: the archive
#: holds `T02n0128a` and `T02n0128b` (and 75 further such pairs) as separate
#: texts. An earlier version of this pattern omitted it, which silently
#: collapsed each pair onto one `witness` node — two different sutras sharing
#: one identity, i.e. exactly the misattribution `CbetaArchiveError` exists to
#: prevent elsewhere in this module.
_CBETA_REF_RE = re.compile(r"([A-Z]{1,2}\d+n[A-Za-z]?\d+[A-Za-z]?)")
#: Taisho-only, deliberately narrower than `_CBETA_REF_RE`: `<cb:docNumber>`
#: cross-references are Taisho numbers, so `resolve_taisho_number()` must not
#: resolve one onto a same-numbered text in another collection.
_T_NUMBER_RE = re.compile(r"(T\d+n\d+[A-Za-z]?)")
#: `T08n0251` -> `251`; `T02n0128a` -> `128a`. Leading zeros dropped so the
#: result compares directly against a `<cb:docNumber>` number.
_T_REF_PARTS_RE = re.compile(r"^T(\d+)n0*(\d+[A-Za-z]?)$")


class CbetaArchiveError(Exception):
    """The archive is missing, hash-mismatched, or malformed — fails
    loudly, never falls back to the local_corpus fixture. That fixture is a
    different, unrelated corpus; silently substituting it would misattribute
    evidence (design doc's standing rule: say so and stop)."""


def verify_archive_hash(path: Path, expected_sha256: str) -> None:
    """Streams the file in chunks; never loads it whole into memory."""
    if not path.is_file():
        raise CbetaArchiveError(f"CBETA archive not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise CbetaArchiveError(
            f"CBETA archive hash mismatch at {path}: expected {expected_sha256}, got {actual}"
        )


def read_verified_entry(
    path: Path, expected_sha256: str, entry_path: str, max_bytes: int = DEFAULT_MAX_ENTRY_BYTES,
) -> bytes:
    """Hash the whole archive, open it as a ZIP, require exactly one
    namelist() match for entry_path (0 or 2+ is an error — unlike some ZIP
    libraries, Python's zipfile permits duplicate names, so this check is
    load-bearing here, not defensive theater), read it under a size cap,
    then re-hash the whole archive a second time and compare again before
    returning. Catches a file swapped mid-read — a real, not hypothetical,
    concern for a large archive a researcher might re-download while a COHORT
    process has it open; the check is cheap (once per fetch, not a hot
    path)."""
    verify_archive_hash(path, expected_sha256)
    with zipfile.ZipFile(path) as zf:
        matches = [n for n in zf.namelist() if n == entry_path]
        if not matches:
            raise CbetaArchiveError(f"entry not found in archive: {entry_path!r}")
        if len(matches) > 1:
            raise CbetaArchiveError(f"entry appears more than once in archive: {entry_path!r}")
        info = zf.getinfo(entry_path)
        if info.file_size > max_bytes:
            raise CbetaArchiveError(
                f"entry {entry_path!r} is {info.file_size} bytes, exceeding the {max_bytes}-byte cap"
            )
        with zf.open(entry_path) as fh:
            data = fh.read()
    verify_archive_hash(path, expected_sha256)
    return data


def find_text_content_start(document: bytes) -> int:
    """Locate `<teiHeader>...</teiHeader>`, then the first `<text` tag
    after it closes; return the byte offset right after that tag's closing
    `>`. Raises if the header or text tag is missing or out of order — a
    minimal hand-rolled scan, not a full XML parser."""
    header_start = document.find(b"<teiHeader")
    if header_start == -1:
        raise CbetaArchiveError("no <teiHeader> found in document")
    header_end = document.find(b"</teiHeader>", header_start)
    if header_end == -1:
        raise CbetaArchiveError("<teiHeader> is never closed")
    header_end += len(b"</teiHeader>")
    text_start = document.find(b"<text", header_end)
    if text_start == -1:
        raise CbetaArchiveError("no <text> element found after </teiHeader>")
    tag_close = document.find(b">", text_start)
    if tag_close == -1:
        raise CbetaArchiveError("<text> tag is never closed")
    return tag_close + 1


def locate_span(source: bytes, excerpt: str) -> tuple[int, int]:
    """Byte offsets of a unique occurrence of `excerpt` in `source`; raises
    if absent or non-unique. Deliberately searches only the post-header
    body passed in by the caller, not the whole document — an excerpt that
    also happens to appear in header metadata should not make a genuine,
    unique body occurrence look ambiguous. This is a cleaner separation
    than checking "found position falls before text_start" after searching
    the whole document: header content is metadata, not evidence, and
    shouldn't participate in the evidentiary uniqueness check at all."""
    needle = excerpt.encode("utf-8")
    first = source.find(needle)
    if first == -1:
        raise CbetaArchiveError(f"excerpt not found in source text: {excerpt!r}")
    second = source.find(needle, first + 1)
    if second != -1:
        raise CbetaArchiveError(f"excerpt is not unique in source text: {excerpt!r}")
    return first, first + len(needle)


def _cbeta_ref_from_entry_path(entry_path: str) -> str:
    match = _CBETA_REF_RE.search(Path(entry_path).name)
    if not match:
        raise CbetaArchiveError(f"could not extract a CBETA ref from entry path: {entry_path!r}")
    return match.group(1)


class CbetaReader(Source):
    source_name = "cbeta"
    #: not "local_rights_held" — the restriction is real (CC BY-NC-SA-
    #: equivalent), and the access_mode string should say so rather than
    #: imply an unrestricted local corpus.
    access_mode = "local_rights_held_restricted"

    LICENSE_NOTE = (
        "CC BY-NC-SA-equivalent: non-commercial, attribution, share-alike, "
        "version and intact-header required"
    )

    def __init__(
        self, archive_path: str | Path, expected_sha256: str, *,
        version: str = "v061", max_entry_bytes: int = DEFAULT_MAX_ENTRY_BYTES,
        index: dict[str, list[str]] | None = None,
        fts=None,
    ) -> None:
        self.archive_path = Path(archive_path)
        self.expected_sha256 = expected_sha256
        self.version = version
        self.max_entry_bytes = max_entry_bytes
        #: optional hand-maintained `entry_path -> known excerpts` mapping
        #: (docs/handoff.md "suggested first session", step 4) — never a
        #: full-corpus index. Loaded by the caller from wherever it likes;
        #: this class stores only what it's given, and never persists it
        #: back into the repository itself (the excerpts are corpus bytes).
        self.index = index
        #: optional `cbeta_fts.CbetaFtsIndex` — the full-corpus index. Takes
        #: precedence over `index` when both are supplied, because otherwise
        #: `search()` results would depend on which source happened to be
        #: passed. The corpus-wide index covers every citable span of every
        #: entry, with two deliberate exclusions (runs below
        #: `cbeta_fts.MIN_RUN_CHARS`, and runs bearing no CJK), so a hand
        #: index listing only such spans would go unused — no real one does.
        #: Typed loosely to keep this module importable without `cbeta_fts`,
        #: which imports from it.
        self.fts = fts
        self._taisho_index: dict[str, set[str]] | None = None
        verify_archive_hash(self.archive_path, expected_sha256)  # fail at construction, not mid-run

    def _taisho_number_index(self) -> dict[str, set[str]]:
        """Lazily map Taisho number -> witness refs, from the archive's own
        entry listing. Built on first use rather than at construction: it
        needs the full namelist, which callers that only ever `fetch()` a
        known ref should not pay for."""
        if self._taisho_index is None:
            idx: dict[str, set[str]] = {}
            with zipfile.ZipFile(self.archive_path) as zf:
                for name in zf.namelist():
                    if not name.startswith(CBETA_ENTRY_PREFIX) or not name.endswith(".xml"):
                        continue
                    match = _T_NUMBER_RE.search(Path(name).name)
                    if not match:
                        continue
                    parts = _T_REF_PARTS_RE.match(match.group(1))
                    if parts:
                        idx.setdefault(parts.group(2).lower(), set()).add(match.group(1))
            self._taisho_index = idx
        return self._taisho_index

    def resolve_taisho_number(self, number: str) -> list[str]:
        """Witness refs for a bare `<cb:docNumber>` Taisho number, e.g.
        `"251"` -> `["T08n0251"]`.

        Returns **every** candidate, sorted, and leaves the caller to refuse
        an ambiguous one — it must not guess. Two ways ambiguity really
        arises in v061:

        - a text spanning several volumes shares one number (`220` ->
          `T05n0220`, `T06n0220`, `T07n0220`);
        - `<cb:docNumber>` sometimes writes a bare number where the archive
          distinguishes lettered siblings (`1138` vs `T20n1138a`/`b`). An
          exact match wins outright; only when there is none does the
          letter-insensitive fallback apply, and then only its full
          candidate set is returned, never an arbitrary pick.
        """
        idx = self._taisho_number_index()
        key = number.strip().lower()
        if key in idx:
            return sorted(idx[key])
        stripped = key.rstrip("abcdefghijklmnopqrstuvwxyz")
        candidates = {
            ref
            for k, refs in idx.items()
            if k.rstrip("abcdefghijklmnopqrstuvwxyz") == stripped
            for ref in refs
        }
        return sorted(candidates)

    def search(self, query: str, max_results: int = 20) -> list[SearchHit]:
        """Full-corpus `fts` index if one is attached, else the
        hand-maintained `index` mapping, else refuse.

        Every hit's `ref` is fetchable: both paths only ever return an
        excerpt that is a unique contiguous substring of its document (see
        `cbeta_fts`'s docstring), so `fetch()` on a search result cannot fail
        the uniqueness check."""
        if self.fts is not None:
            return [
                SearchHit(
                    ref=f"{entry_path}::{excerpt}",
                    title=_cbeta_ref_from_entry_path(entry_path),
                    snippet=excerpt,
                )
                for entry_path, excerpt in self.fts.search(query, max_results=max_results)
            ]
        if self.index is None:
            raise NotImplementedError(
                "CbetaReader has no search index. Build the full-corpus index "
                "(scripts/build_cbeta_index.py) and pass it as `fts=`, or pass a "
                "hand-maintained `index=` mapping; fetch() by a caller-supplied "
                "'entry_path::excerpt' ref works either way."
            )
        hits: list[SearchHit] = []
        for entry_path, excerpts in self.index.items():
            for excerpt in excerpts:
                if query not in excerpt:
                    continue
                hits.append(SearchHit(
                    ref=f"{entry_path}::{excerpt}",
                    title=_cbeta_ref_from_entry_path(entry_path),
                    snippet=excerpt,
                ))
                if len(hits) >= max_results:
                    return hits
        return hits

    def fetch(self, ref: str) -> SourceRecord:
        """`ref` is `"entry_path::excerpt_text"` — the caller already knows
        which juan/text and which excerpt it wants; this reader's job is
        verifying and extracting it exactly, not discovering it. Returns
        the full extracted `<text>` body as `SourceRecord.text` (not just
        the excerpt) so a later `verify_exact_span()` re-fetch remains a
        meaningful re-check against searchable source text, rather than a
        trivially-true comparison of the excerpt against itself — while
        still validating the excerpt's presence and uniqueness here, at
        fetch time, before this record is trusted as evidence at all."""
        if "::" not in ref:
            raise CbetaArchiveError(f"malformed ref, expected 'entry_path::excerpt': {ref!r}")
        entry_path, excerpt = ref.split("::", 1)
        if not entry_path.startswith(CBETA_ENTRY_PREFIX) or ".." in entry_path:
            raise CbetaArchiveError(f"entry path outside the expected CBETA layout: {entry_path!r}")

        document = read_verified_entry(
            self.archive_path, self.expected_sha256, entry_path, self.max_entry_bytes
        )
        text_start = find_text_content_start(document)
        body = document[text_start:]
        locate_span(body, excerpt)  # validated for presence/uniqueness; raises otherwise

        cbeta_ref = _cbeta_ref_from_entry_path(entry_path)
        return SourceRecord(
            ref=ref,
            title=cbeta_ref,
            text=body.decode("utf-8"),
            witness_ref=cbeta_ref,
            locator=entry_path,
            note=f"CBETA {self.version}, {entry_path} — {self.LICENSE_NOTE}",
        )
