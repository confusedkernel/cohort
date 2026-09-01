# Development handoff

## Outcome and current phase

This repository is a working, tested evidence-graph system for supervised
multi-agent textual research (`DESIGN.md` for the design, `ROADMAP.md` for
architecture/tech-stack/build-order — read both before changing anything).
It is not a prototype of an idea; it runs, live, against a real model.

**What's actually been proven, not just written**: 136 tests pass
(`pytest -q`); `demo.py` runs end-to-end with no corpus or API key needed;
`scripts/smoke_openrouter.py` has completed a real OpenRouter call;
`scripts/run_swarm_demo.py` has completed two *concurrent* real agents
against OpenRouter, each with distinct declared scope, each correctly
finding and attesting its own passage, both writes landing safely in one
shared graph.

**The one real blocker, and the reason this handoff exists**: none of that
has ever touched real Buddhist text. Every live run so far used
`examples/local_corpus`, a 4-poem public-domain fixture, explicitly
disclaimed in its own README as "illustrative, never a finding — not the
development corpus." The actual development corpus was decided weeks ago
(see `ROADMAP.md`'s "Scope revision"): **CBETA v061**
(`CBETA_電子佛典_xml_v061_20210710.zip`). Nobody on this side of the project
has ever had a copy of it. The user is moving this work to a shared server
specifically because a labmate's parallel project
(`epistemic-swarm`, a different implementation of the same brief) appears
to already have access to it there. If you're reading this on that server:
**getting the real archive in place is the highest-leverage thing you can
do**, full stop — stage 4, a real search index, and the first
corpus-backed demo are all waiting on it, and nothing else productive
requires it.

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
- **Expected SHA-256** (as recorded in `epistemic-swarm/docs/decisions.md`,
  the labmate's repo — re-verify this independently before trusting it for
  anything; it is relayed here, not confirmed by anyone on this side):
  `90a663f212bc854e6a758ed06c74776cef5cbf8e7040d0192ff3301e6f7158f2`
- **A concrete lead on where a copy might already exist**: the same file in
  `epistemic-swarm` warns *"Do not substitute the convenient
  `/mnt/md0/cckf/corpus/Bookcase/CBETA/XML` tree: a checked document differs
  from the archive copy... The transformed `/mnt/md0/corpus/cbeta` variants
  are derivative analysis inputs, not canonical source evidence."* That
  implies CBETA data already sits somewhere on shared lab infrastructure
  under `/mnt/md0/...` — check there first if you're on a machine with
  access to it. But per that same warning: **that convenient tree is not
  the canonical archive**. Don't point `cohort` at it directly or treat it
  as equivalent; the actual `.zip`, hash-verified, is what
  `cohort/sources/cbeta_reader.py` expects.
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
  access, TEI header-skipping, unique-span excerpt location) —
  **`CbetaReader.search()` deliberately raises `NotImplementedError`**;
  only caller-supplied `fetch("entry_path::excerpt")` works, because there's
  no index to build without the real archive.
- `AttestationWorker` (OpenRouter-backed, stdlib `urllib` transport, no
  client library) with two tools (`find_attestations`, `propose_conjecture`)
  and `run_swarm()` for real concurrent multi-agent execution.
- Agent identity (`register_agent`, `AgentProfile`, `agent_report()` as a
  pure contribution count, deliberately not a reputation score).

## What does not exist

- The real CBETA archive, anywhere (see above).
- A search index over any real corpus (`CbetaReader.search()` is a stub
  that refuses to run).
- Any `find_attestations`/`propose_conjecture` run against real Buddhist
  text — every live run so far used the Tang-poem fixture.
- Stage 4 (`parallel_of`/`descends_from` extraction, contradiction
  surfacing) — blocked on the archive, not started.
- The researcher UI (stage 5's other half) — tech stack decided (FastAPI +
  separate JS/React frontend, see `ROADMAP.md`), nothing built.
- Reputation scoring (agent-society step 5) — deliberately deferred, not
  blocked on anything.
- ATELIER integration (stage 6) — not started, not needed yet.

## Environment

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q                # should be 136 passed
.venv/bin/python demo.py           # no corpus, no API key needed
cp .env.example .env               # then fill in OPENROUTER_API_KEY / OPENROUTER_MODEL yourself —
                                    # never paste a real key into a chat session
.venv/bin/python scripts/smoke_openrouter.py     # one real API call, manual only, never automated
.venv/bin/python scripts/run_swarm_demo.py       # two real concurrent agents, manual only
```

Venvs bake in absolute paths — if this repo gets moved again after being
cloned onto the server, delete and recreate `.venv` rather than trying to
reuse one copied from elsewhere.

## Suggested first session on the server

1. Locate the archive (see above). If it's genuinely not accessible even on
   shared infrastructure, say so and stop rather than substituting
   `examples/local_corpus` or the labmate's derivative `/mnt/md0/corpus/cbeta`
   tree and calling it equivalent — that would misattribute evidence.
2. Verify the hash by hand, then via `CbetaReader`, before anything else.
3. Once verified: read a handful of real CBETA XML files directly (not
   through `cohort` yet) to answer the one open question stage 4 has been
   waiting on — does the corpus carry usable parallel/cross-reference or
   variant-reading (`<app>`/`<rdg>`-style TEI apparatus) markup already?
   That answer determines how close stage 4 actually is once wired up.
4. Only then: design a minimal local index for `CbetaReader.search()` (a
   hand-maintained "entry path → known excerpts" mapping is enough to
   start — a full-corpus FTS index is not required for a first real run),
   wire it in, and run `find_attestations`/`propose_conjecture` against
   real text for the first time.
5. Do not decide the chronology scheme or the rich/Tyler/Chunki division of
   labour unilaterally — both are named as open in `ROADMAP.md` for a
   reason; flag them, don't guess.
