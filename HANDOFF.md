# Development handoff

## Outcome and current phase

This repository is a working, tested evidence-graph system for supervised
multi-agent textual research (`DESIGN.md` for the design, `ROADMAP.md` for
architecture/tech-stack/build-order — read both before changing anything).
It is not a prototype of an idea; it runs, live, against a real model.

**What's actually been proven, not just written**: 167 tests pass
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
(436 occurrences) is a further cross-reference channel worth a look.

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

- A full-corpus search index — only the two-entry hand-maintained
  `cbeta_index.json` exists so far (see above); `CbetaReader.search()` still
  raises `NotImplementedError` when constructed without an `index`.
- `propose_conjecture` run against real Buddhist text — only
  `find_attestations` has been run against the real archive so far.
- Stage 4's remaining pieces: `descends_from` extraction (nothing in the
  markup asserts descent directly — `parallel_of` is what the corpus
  actually states) and contradiction surfacing. The `parallel_of` and
  cross-edition-collation halves are built and live-verified (see above).
- Any use of the `<note type="cf1|cf2|cf3">` cross-reference channel (436
  occurrences in the 300-file sample) — only `<cb:docNumber>` is read so far.
- The researcher UI (stage 5's other half) — tech stack decided (FastAPI +
  separate JS/React frontend, see `ROADMAP.md`), nothing built.
- Reputation scoring (agent-society step 5) — deliberately deferred, not
  blocked on anything.
- ATELIER integration (stage 6) — not started, not needed yet.

## Environment

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q                # should be 167 passed
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
