"""CBETA archive reader — COHORT's confirmed development corpus (ROADMAP.md
"Scope revision"), locally-held but restrictively licensed (CC BY-NC-SA-
equivalent: non-commercial, attribution, share-alike, version and
intact-header requirements — not public domain).

A new module, not an extension of `local_reader.py`: CBETA is a single
hash-verified ZIP archive with TEI-header-skipping and span-location
concerns `LocalReader`'s manifest-driven plain-text-file model doesn't have.

No real archive exists on this machine, or in the labmate's own parallel
project's repo, at the time this was written — only a config path
(`CBETA_ARCHIVE_PATH`) either project would point at once someone actually
downloads it. Corpus bytes never enter this repository; this module is
fully exercised against a synthetic fixture (`tests/test_cbeta_reader.py`).

Witness identity is the bare Taisho T-number (e.g. `T02n0099`), not an
archive-version-qualified string — that's the text's actual scholarly
identity, stable across CBETA archive version bumps, unlike an
archive-internal path. The archive version and entry path are provenance
detail, carried in `SourceRecord.note` (which feeds `WitnessPayload.
source_terms`), not baked into the identity itself.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

from .base import SearchHit, Source, SourceRecord

CBETA_ENTRY_PREFIX = "Bookcase/CBETA/XML/"
DEFAULT_MAX_ENTRY_BYTES = 50_000_000

_T_NUMBER_RE = re.compile(r"(T\d+n\d+)")


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


def _t_number_from_entry_path(entry_path: str) -> str:
    match = _T_NUMBER_RE.search(Path(entry_path).name)
    if not match:
        raise CbetaArchiveError(f"could not extract a Taisho T-number from entry path: {entry_path!r}")
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
    ) -> None:
        self.archive_path = Path(archive_path)
        self.expected_sha256 = expected_sha256
        self.version = version
        self.max_entry_bytes = max_entry_bytes
        #: optional hand-maintained `entry_path -> known excerpts` mapping
        #: (HANDOFF.md "suggested first session", step 4) — never a
        #: full-corpus index. Loaded by the caller from wherever it likes;
        #: this class stores only what it's given, and never persists it
        #: back into the repository itself (the excerpts are corpus bytes).
        self.index = index
        verify_archive_hash(self.archive_path, expected_sha256)  # fail at construction, not mid-run

    def search(self, query: str, max_results: int = 20) -> list[SearchHit]:
        if self.index is None:
            raise NotImplementedError(
                "CbetaReader has no search index — there is no local full-corpus "
                "index to build without deciding on one against the real archive. "
                "fetch() by a caller-supplied 'entry_path::excerpt' ref is what's "
                "implemented; wiring search() to a real index is corpus-integration "
                "work that waits on the actual archive (see ROADMAP.md)."
            )
        hits: list[SearchHit] = []
        for entry_path, excerpts in self.index.items():
            for excerpt in excerpts:
                if query not in excerpt:
                    continue
                hits.append(SearchHit(
                    ref=f"{entry_path}::{excerpt}",
                    title=_t_number_from_entry_path(entry_path),
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

        t_number = _t_number_from_entry_path(entry_path)
        return SourceRecord(
            ref=ref,
            title=t_number,
            text=body.decode("utf-8"),
            witness_ref=t_number,
            locator=entry_path,
            note=f"CBETA {self.version}, {entry_path} — {self.LICENSE_NOTE}",
        )
