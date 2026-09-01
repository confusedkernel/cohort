# Development handoff

## Outcome and current phase

This repository is a working, tested evidence-graph system for supervised
multi-agent textual research (`DESIGN.md` for the design, `ROADMAP.md` for
architecture/tech-stack/build-order — read both before changing anything).
It is not a prototype of an idea; it runs, live, against a real model.

**What's actually been proven, not just written**: 139 tests pass
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
No explicit `parallel_of`-style cross-reference tags turned up in that same
sample, but that's a much smaller, more targeted look than the variant-
reading check and shouldn't be read as a negative result — still open.

`CbetaReader.search()` is no longer an unconditional stub: it now accepts
an optional `index: dict[str, list[str]]` (`entry_path -> known excerpts`)
at construction, per this file's own suggested minimal approach — a
hand-maintained mapping, not a full-corpus index. The actual index lives in
`cbeta_index.json` at the repo root, **gitignored** (its excerpts are corpus
bytes copied from the real archive; see `.gitignore`), and currently has two
entries: the Heart Sutra's 色即是空，空即是色 (T08n0251) and the Diamond
Sutra's closing gatha 一切有為法如夢幻泡影如露亦如電應作如是觀 (T08n0235),
each verified as a real, unique, tag-free substring of its document before
being added.

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
- Stage 4 (`parallel_of`/`descends_from` extraction, contradiction
  surfacing) — the archive and a variant-reading answer both now exist
  (see above), but extraction itself isn't built yet.
- The researcher UI (stage 5's other half) — tech stack decided (FastAPI +
  separate JS/React frontend, see `ROADMAP.md`), nothing built.
- Reputation scoring (agent-society step 5) — deliberately deferred, not
  blocked on anything.
- ATELIER integration (stage 6) — not started, not needed yet.

## Environment

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q                # should be 139 passed
.venv/bin/python demo.py           # no corpus, no API key needed
cp .env.example .env               # then fill in OPENROUTER_API_KEY / OPENROUTER_MODEL yourself —
                                    # never paste a real key into a chat session
.venv/bin/python scripts/smoke_openrouter.py     # one real API call, manual only, never automated
.venv/bin/python scripts/run_swarm_demo.py       # two real concurrent agents, manual only
.venv/bin/python scripts/run_cbeta_demo.py       # one real agent against the real CBETA archive,
                                                  # manual only — needs CBETA_ARCHIVE_PATH in .env too
```

Venvs bake in absolute paths — if this repo gets moved again after being
cloned onto the server, delete and recreate `.venv` rather than trying to
reuse one copied from elsewhere.

## Suggested next session on the server

Steps 1-4 below (locate/verify the archive, answer the markup question,
build a minimal index, run `find_attestations` for real) are now done —
see the update at the top of this file. What's next:

1. Run `propose_conjecture` against real text for the first time — nothing
   has exercised the falsifiability-gate dossier against genuine CBETA
   content yet, only the fixture.
2. Decide whether `cbeta_index.json` needs more than two entries before
   that's useful, or whether a couple of hand-picked passages are enough to
   exercise the conjecture path meaningfully.
3. Take a closer, more deliberate look at whether `parallel_of`-style
   cross-reference markup exists anywhere in the corpus — the 30-file
   sample that answered the variant-reading question didn't find any, but
   it wasn't a targeted search for that specifically.
4. Do not decide the chronology scheme unilaterally — it's named as open in
   `ROADMAP.md` for a reason; flag it, don't guess.
