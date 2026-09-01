# Development handoff

## Outcome and current phase

This repository is a working, tested evidence-graph system for supervised
multi-agent textual research (`DESIGN.md` for the design, `ROADMAP.md` for
architecture/tech-stack/build-order — read both before changing anything).
It is not a prototype of an idea; it runs, live, against a real model.

**What's actually been proven, not just written**: 212 tests pass
(`pytest -q`); `demo.py` runs end-to-end with no corpus or API key needed;
`scripts/smoke_openrouter.py` has completed a real OpenRouter call;
`scripts/run_swarm_demo.py` has completed two *concurrent* real agents
against OpenRouter, each with distinct declared scope, each correctly
finding and attesting its own passage, both writes landing safely in one
shared graph; `scripts/run_cbeta_demo.py` has now done the same against the
real CBETA archive (see below).

**Update, 2026-09-01: the archive blocker is resolved.** The real CBETA v061
archive was located on this shared server at
`/mnt/md0/cckf/corpus/CBETA_電子佛典/CBETA_電子佛典_xml_v061_20210710.zip`
(not the same as, and not derived from, the `/mnt/md0/cckf/corpus/Bookcase/CBETA/XML`
tree — that convenient tree is a separate, unverified extraction and was not
used). Its SHA-256 was computed independently (`shasum -a 256`) and matches
the expected value recorded below:
`90a663f212bc854e6a758ed06c74776cef5cbf8e7040d0192ff3301e6f7158f2`.
`CbetaReader` agrees. `.env`'s `CBETA_ARCHIVE_PATH` now points at it.

A random sample of 30 real entries answered the corpus-markup open question
(ROADMAP.md §14, HANDOFF step 3): **29/30 carry real `<app>`/`<lem>`/`<rdg>`
variant-reading TEI apparatus** with genuine edition sigla (e.g. `【CB】` vs
`【金藏】`) — variant-reading extraction for stage 4 is clearly feasible.
A second, targeted probe (300 random entries) then answered the
parallel/cross-reference half, which the first sample had missed because it
looked for generic TEI pointer elements. Those are indeed rare (`<ref>` in
16/300 files, `<cit>`/`<cb:tt>` in 5). **The real cross-reference channel is
`<cb:docNumber>`**: 14 of 65 docNumber elements carry a bracketed parallel
list, e.g. `No. 991 [Nos. 989, 992, 993]`. Two distinct semantics live in
that bracket, and they are *not* interchangeable:

- a bare list (`[Nos. 989, 992, 993]`) asserts parallel texts;
- a `cf.` list (`[cf. No. 2810]`, `[cf. No. 220(4 or 5) etc.]`) is a
  curatorial "compare", sometimes deliberately vague.

This matters more than it looks: in COHORT a `parallel_of` edge has teeth —
`independent_support()` flips `independent` to False the moment one links two
supporting witnesses. Minting `parallel_of` from a vague `cf. ... etc.` would
silently *suppress* independent support on weak evidence, which is the
failure mode the whole design exists to prevent. So the extractor should emit
`parallel_of` only for unambiguous bare lists, and leave `cf.` references out
until there's a considered representation for them. Two further parsing
notes: sub-references appear inside the brackets (`No. 26(131)`,
`No. 99(449-450)`), and at least one bracket contains an embedded `<lb/>`
tag, so tags must be stripped before parsing.

The variant/collation half is pervasive and directly usable: **271 of 300
files contain an `<app>` citing two or more distinct editions.** The sigla
are frequently *joint* — `【宋】【元】【明】【宮】` appears as a single `wit`
value 2155 times — which is exactly the shared-descent-vs-independent
-confirmation distinction `CROSS_EDITION_COLLATION` and
`independent_support()` exist to model. `<note type="cf1|cf2|cf3|cf.">`
(436 occurrences in that 300-file sample; ~31,800 corpus-wide, measured
later) is a further cross-reference channel worth a look.

The closed vocabulary already covers all of this: `parallel_of`,
`descends_from`, and `CROSS_EDITION_COLLATION` exist, and
`independent_support()` already consumes descent/parallel edges. Stage 4
needed no new types — only extraction.

**Update: stage 4's extraction layer is built, tested and live-verified.**

- `cohort/sources/cbeta_markup.py` — pure parsers for both channels, no
  graph or I/O dependency. `parse_parallel_refs()` classifies
  `<cb:docNumber>` brackets into `asserted` / `compare_only` (`cf.`) /
  `part_of` / `unparsed`, splitting `cf.` **by position** because the corpus
  mixes both in one bracket; it expands ranges, keeps sub-references
  (`278(22)`) out of identity, strips tags embedded mid-list, and reports a
  non-Taisho bracket (`[~M. 118... Ānāpānasati sutta.]`) unparsed rather than
  half-reading digits out of it. `parse_apparatus()` reads `<app>`/`<lem>`/
  `<rdg>`, and `edition_families()` tallies edition groups **as written** —
  joint sigla are never split, since splitting a shared-descent family into
  separate confirmations is the exact error §4 is about.
- `cohort/tools/link_parallels.py` — writes `parallel_of` edges, with two
  standing refusals: only `asserted` references become edges (never `cf.`
  or `Part of`), and only witnesses **already in the graph** are linked —
  an absent parallel is reported as a candidate, never proposed as a witness
  node, because that would assert a source record nobody has read. Idempotent.
- `cohort/tools/collate_editions.py` — records a `CROSS_EDITION_COLLATION`
  verification per witness, reporting edition families and flagging modern
  editorial emendations (`【CB】`/`resp="CBETA…"`). Every record carries a
  `limitations` string stating plainly that apparatus describes variants
  *within one document* and therefore says nothing about whether two
  witnesses are independent of each other — so an `A3_INDEPENDENCE_CHECKED`
  label can't be misread as a stronger claim than it is.
- `scripts/run_stage4_demo.py` — **the thesis, on real text, with no model
  call**: T08n0250/0251/0252 are three different Chinese translations of the
  Heart Sutra that all contain 色即是空，空即是色. Recorded naively they read as
  three independent confirmations (`independent=True`). After
  `link_parallels` reads CBETA's own cross-reference lists, `attesting_count`
  stays 3 while `independent` flips to False across all 3 pairs — agreement
  between parallel translations is shared descent. `demo.py` could only ever
  show this with a hand-added edge; this derives it from the corpus.

**The parser is now validated corpus-wide.** `scripts/scan_parallels.py`
(read-only, no API, ~8s for all 20,190 entries) runs `parse_parallel_refs()`
over the whole archive and writes three artifacts to `~/cbeta_scan/`:
`parallel_map.jsonl` (every entry's cross-references, with asserted numbers
resolved to witness refs), `unparsed.txt` (**every bracket the parser
declined, deduped, with an example entry** — the file actually worth reading),
and `summary.txt`.

Results: 935 entries carry cross-references; **1,240 asserted references, of
which 1,203 resolve 1:1**; 607 `cf.`; 6 `Part of`; 37 declined as ambiguous
(`220` alone accounts for 20, since it legitimately spans three volumes); 0
unknown; and **13 distinct brackets declined**, every one inspected and
legitimately hard:

- CBETA/Taisho apparatus inline in the docNumber (`Nos. 633, 634【CB】，1【大】41`)
  — half-reading these yields mashed-together numbers like `279229`, so
  refusing is the only safe behaviour;
- Pali references (`~M. 118【CB】，5【大】85, Ānāpānasati sutta.`), not Taisho;
- one genuine typo in the corpus: `cf. N0. 1524` (a zero, not "No.");
- a fascicle-structured list (`Fasc. 1-39 = Nos. ...; Fasc. 40 = ...`) and
  lettered range endpoints (`1060-1062A`), all `cf.` or structurally complex.

The scan also drove one parser refinement: a `;`-delimited chunk with no
digits is an annotation, not a reference list (the corpus appends a Chinese
title this way, `Nos. 450, 451; 灌頂經卷第十二`), so it is dropped rather than
allowed to fail the residue check and discard the good numbers next to it.
Dropping a digit-free chunk cannot introduce a number, so it cannot
manufacture a reference — and a chunk that *does* carry digits must still
parse cleanly, which is why the `Fasc.` case above is still refused. That
recovered 6 real parallels and took declined brackets from 16 to 13.

Finally, the scan sized the `<note type="cf*">` channel HANDOFF flagged as
unexplored: **~31,800 occurrences** (cf1 23,838; cf2 6,061; cf. 1,243; cf3
608; cf4 28; cf5 8; cf6 4). Nothing reads it yet, and it is much larger than
the `<cb:docNumber>` channel — worth a look before assuming the parallel data
is exhausted.

**A pre-existing bug fixed on the way.** `_T_NUMBER_RE` was `T\d+n\d+`, which
drops the letter suffix that distinguishes lettered siblings — so
`T02n0128a` and `T02n0128b` both produced `witness:T02n0128`, silently
merging two different texts into one witness node (77 such refs in v061).
The pattern now keeps the letter. `CbetaReader.resolve_taisho_number()` maps
a bare docNumber number onto witness refs via the archive's own listing and
**returns every candidate rather than guessing** — number `220` legitimately
spans `T05n0220`/`T06n0220`/`T07n0220`, and `1138` has lettered siblings;
`link_parallels` refuses both cases and reports them in `unresolved`.

`CbetaReader.search()` is no longer an unconditional stub: it now accepts
an optional `index: dict[str, list[str]]` (`entry_path -> known excerpts`)
at construction, per this file's own suggested minimal approach — a
hand-maintained mapping, not a full-corpus index. The actual index lives in
`cbeta_index.json` at the repo root, **gitignored** (its excerpts are corpus
bytes copied from the real archive; see `.gitignore`), and currently has four
entries, each verified as a real, unique, tag-free substring of its document
before being added: 色即是空，空即是色 in all three Heart Sutra translations
(T08n0250, T08n0251, T08n0252 — the shared phrase `run_stage4_demo.py` turns
on), and the Diamond Sutra's closing gatha
一切有為法如夢幻泡影如露亦如電應作如是觀 (T08n0235).

Because the index is gitignored, a fresh clone has none: both
`scripts/run_cbeta_demo.py` and `scripts/run_stage4_demo.py` exit with a
message naming exactly what they expect rather than failing obscurely.

**Update: the full-corpus search index is built and working.**

`cohort/sources/cbeta_fts.py` builds a persistent SQLite FTS5 index, reusing
the character-unigram trick `local_reader.py` already relies on (FTS5's
tokenizer treats an unbroken CJK run as one token, so `MATCH "寂寞"` against
running Chinese matches nothing; indexing a space-separated unigram copy and
phrase-querying it restores exact character-sequence matching without a
segmenter).

The design constraint that shaped everything else: **what is searchable and
what is citable are the same thing.** `fetch()` resolves a ref only if the
excerpt is a *unique, contiguous, tag-free* substring of the body, so the
index stores exactly those spans — maximal tag-free runs occurring once in
their document — and nothing else. An index that could return more would hand
callers hits `fetch()` then refuses, which is worse than no hit. Two
consequences worth knowing:

- CBETA marks line beginnings with `<lb/>` every ten to twenty characters, so
  a query longer than a line generally matches nothing. That is `fetch()`'s
  boundary, not a new one.
- FTS5 serves only as a *candidate filter* (the indexed token stream
  concatenates a document's runs, so a phrase straddling two runs can match
  the index while existing nowhere contiguously). Every candidate is
  re-checked in Python, so the guarantee holds by construction — there is a
  test asserting every search hit round-trips through `fetch()`.

Build it with `scripts/build_cbeta_index.py` (explicit and manual — never
something a constructor does). Query it from `scripts/search_cbeta.py`, or by
passing `fts=CbetaFtsIndex(path, sha)` to `CbetaReader`. The index records the
archive SHA-256 it was built from and **refuses to serve a reader expecting a
different archive** — otherwise an index could answer queries with offsets
into a file nobody verified.

Measured on the real archive: build 432s / 1.14 GB / 20,190 entries, 0
skipped, 15.28M citable runs (1.43M runs dropped as non-unique, 1.13M as too
short or non-CJK). Corpus-wide search is ~0.04-0.8s and never touches the
archive. `fetch()` costs ~1.4s warm, because it re-hashes the whole archive
twice by design; that stays as it is — the guarantee is worth 1.4s.

**One characteristic to know before trusting a result set**: search returns
corpus order, so `max_results` truncates *arbitrarily* rather than by
relevance. Common phrases are genuinely common — 色即是空 occurs in 412
documents across 13 collections, 如是我聞 in 1,462 — so taking the top five
yields five alphabetically-early witnesses, not the five most pertinent. No
ranking is applied on purpose: BM25 would favour short commentaries over the
scriptures they quote, encoding a scholarly judgement about which witnesses
matter into infrastructure, which §5 principle 2 refuses. When a conjecture
rests on a truncated result set, that belongs in
`ConjecturePayload.selection_risks`.

**Update: the researcher UI (stage 5) is built and serving — read-only.**

`cohort/ui/api.py` is a FastAPI JSON API over `graph.py`'s reader surface;
`cohort/ui/frontend/` is a React + Vite app that builds into
`cohort/ui/static/`, which the API mounts when present. Both live behind the
optional `ui` extra, so the core library and CLI never require them
(`pip install -e '.[ui]'`).

```bash
.venv/bin/python scripts/seed_demo_graph.py --force   # real CBETA data, no API key
cd cohort/ui/frontend && npm install && npm run build
.venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite   # http://127.0.0.1:8000
```

**Read-only is a position, not a phase.** Every request opens the projection
through the new `Graph.open_read_only()`, which takes no writer lock, so the
UI serves *while an agent run is writing* — there is a test asserting exactly
that. It also cannot write: SQLite is opened `mode=ro`, migrations are skipped
(applying one is itself a write, so an out-of-date projection is refused
rather than misread), and no `EventLog` is attached, which makes every
mutating method fail through the existing `event_log_or_raise()` guard rather
than a parallel check that could drift from it. A test asserts the app exposes
no non-GET routes.

**Accept/reject is deliberately absent, and this is the open decision.**
DESIGN.md §13 puts it in stage 5, but those are researcher *writes*, and a
writing UI would hold the exclusive lock for as long as a browser tab is open
— stopping every agent run in the meantime. That concurrency question deserves
a decision of its own rather than being settled by whichever endpoint got
written first.

**The frontend honours §10's requirements as requirements**, since a naive
rendering "flattens exactly the epistemics that justify the system": node
status is a coloured bar on every node rather than a tooltip; `parallel_of`
and `descends_from` are drawn thicker and dashed in a distinct colour, labelled
"**discounts** support" in the legend, and flagged `discounts: true` by the
API so the frontend cannot omit the distinction by accident; `contradicts` is
as heavy as `attests`; every node opens a provenance panel with authorship,
verifications (including their `limitations` text), edges both ways, and the
`independent_support` block. Layout is a deterministic evidence chain
(witness → passage → claim) rather than a force simulation, which would place
the same graph differently on every load — a poor property for something meant
to be read and cited. Audit nodes (`verification`, `decision`) are hidden by
default as bookkeeping rather than evidence, behind a toggle.

`scripts/seed_demo_graph.py` builds the demo graph from the **real archive**,
not a fixture: three Heart Sutra translations, hash-verified, with
`parallel_of` edges read out of CBETA's own cross-references, giving
`attesting_count = 3, independent = False`. Its one hand-authored node is a
conjecture left at `proposed` with no `tests` edge — the falsifiability gate
would refuse to attest it, which is precisely the state worth being able to
see. It is hand-authored because `propose_conjecture`'s live path against real
text still has not been run, and staging a fake model run would misrepresent
what has been verified.

Two things found while building it: `Graph` had **no public way to list
nodes** (only the opinionated `citable()`/`rejected()`), now `Graph.nodes()`;
and node ids routinely contain `#` (a passage ref is `{witness}#{excerpt}`),
which in a URL path silently truncates at the fragment — so `/api/node` and
`/api/agent` take the id as a query parameter, with a regression test.

**A second pre-existing bug fixed here.** `CbetaReader` assumed Taisho
throughout: `_t_number_from_entry_path` matched only `T…` refs, so `search()`
*and* `fetch()` raised on every other collection — 11,208 of the archive's
20,190 entries, including all 4,000-plus of X (卍續藏). Witness identity is
now any CBETA canonical ref (`T02n0099`, `X10n0249`, `J01nA042`,
`B00na001`, `ZW01n0014a`), validated against all 20,190 filenames with zero
failures (4,852 distinct texts). This is additive — Taisho refs are unchanged
— and Taisho stays privileged in exactly one place,
`resolve_taisho_number()`, because `<cb:docNumber>` cross-references are
Taisho numbers.

`scripts/run_cbeta_demo.py` (same manual-only discipline as
`scripts/run_swarm_demo.py`) has now run one real agent, via OpenRouter,
calling `find_attestations` against the real archive for both claims above
— **the first corpus-backed demo this project has run**. Both passages were
located, attested, and their witnesses correctly carry the CC BY-NC-SA-
equivalent license note (`WitnessPayload.source_terms`, populated from
`SourceRecord.note` — this wiring was previously missing in
`find_attestations.py` despite the schema field existing for exactly this
purpose; fixed as part of this run, with a regression test in
`tests/test_tools.py`). 139 tests pass (was 136; three new tests cover the
`index`-backed `search()` and the `source_terms` fix).

**What's still open, deliberately not decided unilaterally** (ROADMAP.md
§14): the chronology scheme. `propose_conjecture` has also not yet been run
against real text — only `find_attestations` has, so far.

## Read first

1. `DESIGN.md` — the design spec. Section 0's standing rule: *"when a rule
   here cannot be honoured, say so and stop. Do not implement something
   that looks like it honours the rule."* Follow that rule literally in
   everything below.
2. `ROADMAP.md` — structure, tech stack, design ideology, build order, and
   the "Scope revision" section documenting every deliberate departure from
   `DESIGN.md`'s original text (each one quoted and annotated in place, not
   silently changed).
3. This file, for what to do first.

## The CBETA archive: what's known, what to check

- **Target file**: `CBETA_電子佛典_xml_v061_20210710.zip`.
- **Expected SHA-256**, independently verified against the actual archive
  file on this server (`shasum -a 256`) — do not skip re-verifying this on
  any new machine before trusting it for anything:
  `90a663f212bc854e6a758ed06c74776cef5cbf8e7040d0192ff3301e6f7158f2`
- **A concrete lead on where a copy might already exist**: shared lab
  infrastructure under `/mnt/md0/...` is worth checking first if you're on
  a machine with access to it — but watch for convenient-looking derivative
  trees (e.g. an already-extracted `.../Bookcase/CBETA/XML` directory, or a
  transformed plain-text variant): a checked document in one of those can
  differ from the archive copy and represents a separate, unidentified
  version. **Those trees are not the canonical archive.** Don't point
  `cohort` at one directly or treat it as equivalent; the actual `.zip`,
  hash-verified, is what `cohort/sources/cbeta_reader.py` expects.
- **License, already handled in code, not just docs**: CBETA is CC
  BY-NC-SA-equivalent — non-commercial, attribution, share-alike, version,
  intact-header requirements — **not public domain**. `ROADMAP.md`'s "Scope
  revision" explains how this was reconciled with `DESIGN.md` §2's
  "public-domain or locally-held" rule (read disjunctively: locally-held
  qualifies on its own, with terms preserved). Corpus bytes must never be
  committed to this repository, ever — `.gitignore` doesn't currently need
  a rule for this because no corpus files exist yet, but if you add any,
  add the ignore rule in the same change.

**Once you have the archive:**

```bash
# 1. Verify it's the expected file before touching cohort at all:
shasum -a 256 /path/to/CBETA_電子佛典_xml_v061_20210710.zip
# compare against the hash above by hand — do not skip this step

# 2. Point cohort at it (see .env.example for the full variable list):
echo 'CBETA_ARCHIVE_PATH=/path/to/CBETA_電子佛典_xml_v061_20210710.zip' >> .env

# 3. Confirm cohort's own reader agrees the hash matches:
.venv/bin/python -c "
from cohort.sources.cbeta_reader import CbetaReader
r = CbetaReader('/path/to/CBETA_電子佛典_xml_v061_20210710.zip',
                '90a663f212bc854e6a758ed06c74776cef5cbf8e7040d0192ff3301e6f7158f2')
print('archive verified, reader constructed OK')
"
```

If the hash doesn't match: **stop, don't proceed, don't substitute a
different tree** (per `DESIGN.md`'s standing rule — say so and stop). A
mismatched archive is a different, unidentified version, and provenance
claims built on it would be false from the start.

## What exists

- Full write-boundary system: closed vocabulary, append-only event log as
  ground truth, SQLite projection, rebuild-and-diff fidelity,
  single-writer discipline (`cohort/graph.py`, `cohort/eventlog.py`,
  `cohort/schemas.py`, `cohort/errors.py`, `cohort/migrations.py`).
- Verification/assurance model (`Graph.verify()`, `assurance_for()`,
  `verify_exact_span` tool) and independent payload-integrity hashing
  (`Graph.verify_integrity()`).
- Source interface + two readers: `LocalReader` (manifest-driven plain text,
  used by every fixture/test) and `CbetaReader` (hash-verified archive
  access, TEI header-skipping, unique-span excerpt location). `fetch()`
  (`"entry_path::excerpt"`) always works; `search()` still raises
  `NotImplementedError` when constructed without an `index`, but now
  accepts an optional hand-maintained `index: dict[str, list[str]]`
  (`entry_path -> known excerpts`) — see the update at the top of this
  file and `cbeta_index.json` (gitignored).
- `AttestationWorker` (OpenRouter-backed, stdlib `urllib` transport, no
  client library) with two tools (`find_attestations`, `propose_conjecture`)
  and `run_swarm()` for real concurrent multi-agent execution.
- Agent identity (`register_agent`, `AgentProfile`, `agent_report()` as a
  pure contribution count, deliberately not a reputation score).

## What does not exist

- Relevance ranking over search results — deliberately absent, see the
  full-corpus index section above. Results come back in corpus order.
- `propose_conjecture` run against real Buddhist text — only
  `find_attestations` has been run against the real archive so far.
- Stage 4's remaining pieces: `descends_from` extraction (nothing in the
  markup asserts descent directly — `parallel_of` is what the corpus
  actually states) and contradiction surfacing. The `parallel_of` and
  cross-edition-collation halves are built and live-verified (see above).
- Any use of the `<note type="cf1|cf2|cf3">` cross-reference channel (436
  occurrences in the 300-file sample) — only `<cb:docNumber>` is read so far.
- Accept/reject **from** the UI (stage 5's remaining half) — see the UI
  section above for why it is a decision rather than an omission.
- Reputation scoring (agent-society step 5) — deliberately deferred, not
  blocked on anything.
- ATELIER integration (stage 6) — not started, not needed yet.

## Environment

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q                # should be 212 passed
.venv/bin/python demo.py           # no corpus, no API key needed
cp .env.example .env               # then fill in OPENROUTER_API_KEY / OPENROUTER_MODEL yourself —
                                    # never paste a real key into a chat session
.venv/bin/python scripts/smoke_openrouter.py     # one real API call, manual only, never automated
.venv/bin/python scripts/run_swarm_demo.py       # two real concurrent agents, manual only
.venv/bin/python scripts/run_cbeta_demo.py       # one real agent against the real CBETA archive,
                                                  # manual only — needs CBETA_ARCHIVE_PATH in .env too
.venv/bin/python scripts/run_stage4_demo.py      # stage 4 on real text: shared descent recognised.
                                                  # No API key and no model call — needs only
                                                  # CBETA_ARCHIVE_PATH and cbeta_index.json
.venv/bin/python scripts/build_cbeta_index.py    # full-corpus FTS index: ~7 min, ~1.1 GB, one-off
.venv/bin/python scripts/search_cbeta.py 色即是空  # search the whole corpus (needs that index)
.venv/bin/python scripts/scan_parallels.py       # corpus-wide parser validation, ~8s, read-only
                                                  # -> ~/cbeta_scan/{parallel_map.jsonl,unparsed.txt,summary.txt}
```

Venvs bake in absolute paths — if this repo gets moved again after being
cloned onto the server, delete and recreate `.venv` rather than trying to
reuse one copied from elsewhere.

## Suggested next session on the server

Locating/verifying the archive, answering the markup question, building a
minimal index, running `find_attestations` for real, and stage 4's
`parallel_of` + cross-edition-collation extraction are all done — see the
updates at the top of this file. What's next:

1. Run `propose_conjecture` against real text for the first time — nothing
   has exercised the falsifiability-gate dossier against genuine CBETA
   content yet, only the fixture. This is the last stage-2/3 capability
   never tried on the real corpus.
2. Wire the two stage 4 tools into `AttestationWorker`'s tool list if agents
   should be able to call them. They are deliberately *not* registered yet:
   both write structure with real epistemic consequences, and letting a
   model mint `parallel_of` edges is a decision worth making explicitly
   rather than by default.
3. Contradiction surfacing — the other half of stage 4, untouched. The
   `contradicts` edge already exists in the vocabulary.
4. Decide whether `cbeta_index.json` needs more entries. A full-corpus FTS
   index remains unbuilt; four hand-picked entries have been enough so far.
5. Do not decide the chronology scheme unilaterally — it's named as open in
   `ROADMAP.md` for a reason; flag it, don't guess.
