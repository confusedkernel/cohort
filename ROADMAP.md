# Roadmap: structure, tech stack, design ideology

## Status note

`DESIGN.md` §11 describes stage 1 (`schemas.py`, `errors.py`,
`eventlog.py`, `graph.py`, 22 tests, a demo) as already built. A full survey
of this repository (`git log`, `git status`, a recursive file search) found
only `DESIGN.md`, zero commits, no remote. **Nothing from stage 1
exists on disk, under any name.** This document treats §11 as the *spec* for
stage 1, not a status report, and plans to build it fresh.

Decisions already made:
- The agent/LLM layer (stage 2's attestation worker, stage 3's conjecture
  generator) uses the **plain Anthropic Python SDK**, not the Agent SDK or a
  third-party framework.
- MEEP's source interface is shaped like ATELIER's `search`/`fetch`
  (`DESIGN.md` §2), and ATELIER's other conventions are the default for
  team consistency (same authors, same Sindia infrastructure track) —
  cited below as `atelier/...` paths.

---

## Design ideology

The part to internalize before writing any stage-1 code, because it's what
the write boundary is *for*.

**The thesis (§1).** Multiple agents produce multiple readings of a
transmitted corpus; disagreement is preserved as structure, not resolved
into one answer. Nothing votes, averages, or scores confidence by counting
agreement. The system may propose something not already in its sources, on
condition that it names what would refute the proposal. The contribution is
methodological infrastructure (工具層), not a claim about textual history
(內容層).

**Why corroboration weighting is rejected, specifically (§4).** The
reference model this was built against weights claims by how many
independent sources back them — a fact-checking model borrowed from
finance. For a transmitted corpus that model is backwards: two witnesses
agreeing usually means shared descent, not independent confirmation.
Counting agreement as corroboration is the exact error stemmatology exists
to prevent. What replaces it: attestation spread across distinct
works/authors, dating confidence with a stated route, explicit
non-independence edges wherever descent or parallelism is known, and
divergence *within* a lineage as the genuinely informative signal. This is
the one argument a general-purpose research swarm can't make, and it's why
`independent_support()` (below) is the single most important function in
the codebase.

**Seven principles (§5), and what each one forces in the code:**

| Principle | Forces in the architecture |
|---|---|
| 1. Event log is ground truth; graph is a projection | `eventlog.py` is append-only and never truncated; `graph.py::rebuild()` replays it into a shadow graph and diffs against the live one — a failing diff is a bug, not a warning |
| 2. Nothing in the graph is *true* | No fact-assertion node type. `claim`/`conjecture` hold text; only `attests`/`contradicts`/`descends_from`/`parallel_of` edges relate them to evidence |
| 3. Agents talk only through the graph | No agent-to-agent messaging designed anywhere, not in stage 2's tool layer, not in stage 5's fan-out. An agent's entire world is: read graph → call a tool → write back |
| 4. Tools are the only writers | Every node/edge write goes through a named `Graph` method; pydantic validates shape, `graph.py` validates state, both before a single SQL statement runs. No agent constructs SQL or graph structure directly |
| 5. Identity comes from the source | `witness`/`passage` node ids are derived from `canonical_ref`, never hashed from agent output. Two agents finding the same passage converge on one node with two authorship records, not two nodes |
| 6. Only the researcher's signature counts | `accept()`/`reject()`/`reopen()` check `authored_by == "researcher"` and raise otherwise; only `citable()` (status == accepted) is usable as a premise or in output |
| 7. Single writer | One `Graph` process holds an exclusive `flock` on a sidecar lock file; a second process attempting to open the same db fails immediately and loudly, not by queueing |

**Anti-goals (§9)** — each is a plausible-looking wrong turn, worth keeping
visible during stage 2+ when the temptation to add "just one" convenience
shows up: consensus-seeking of any kind; confidence scores from edge counts;
a knowledge graph of asserted facts; agent-to-agent conversation; an open
node/edge vocabulary; reimplementing ATELIER's governance inside MEEP;
claiming governance MEEP doesn't have; content-layer claims dressed as a
demo; agent count as a headline number.

---

## Tech stack

Matches ATELIER where ATELIER's choice generalizes; stays stdlib-only where
the design doc explicitly withholds something (no policy file → no
`pyyaml`).

- **Python ≥3.11**, `enum.StrEnum` for the closed vocabulary (an unlisted
  vocabulary string becomes a `pydantic.ValidationError` for free)
- **pydantic v2** (`BaseModel`, `ConfigDict(extra="forbid")`) for every node
  payload, edge, event, and dating record — not dataclasses. These shapes
  are contracts agents must satisfy; validation belongs at the boundary.
  Mirrors `atelier/atelier/schemas/models.py` exactly.
- **stdlib `sqlite3`**, WAL mode, for the graph projection — the only
  database. No ORM.
- **stdlib `json`** for the event log (one JSON object per line), **`uuid`**
  for agent-authored node/edge ids, **`fcntl.flock`** for the single-writer
  lock.
- **pytest** (`dev` extra) — `[tool.pytest.ini_options] testpaths = ["tests"]`,
  same as ATELIER.
- **setuptools** build backend, `pyproject.toml`, no linter/formatter
  configured (ATELIER runs bare — "match the surrounding style").
- **stage 2+: plain `anthropic` SDK**, behind an optional `agents` extra
  (`anthropic>=0.40`) — a tool-use loop over named functions, nothing more.
  No LangChain, no Agent SDK: the tool layer is already the constraint
  surface (Principle 4), so a heavier framework would add machinery the
  design explicitly doesn't need.
- **stage 2+ local reader**: stdlib SQLite FTS5, reimplementing (not
  importing — MEEP stays standalone per §2) the character-unigram trick from
  `atelier/atelier/adapters/local_corpus_adapter.py`. FTS5's default
  tokenizer treats an unbroken CJK run as one token, so `MATCH "寂寞"`
  against a real sentence matches nothing; indexing space-separated
  characters and phrase-querying fixes this without a segmenter dependency.
  Directly relevant since the likely corpus (CBETA/Kanripo, per design doc
  §14) is Classical Chinese.

---

## Project structure

```
meep/
├── pyproject.toml
├── README.md
├── ROADMAP.md                 # this document
├── meep/
│   ├── __init__.py
│   ├── schemas.py              # closed vocabulary: nodes, edges, events, dating
│   ├── errors.py                # one exception per rule
│   ├── eventlog.py               # append-only JSONL, never truncated
│   └── graph.py                   # SQLite projection, the only writer
├── tests/
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_eventlog.py
│   └── test_graph.py
└── demo.py                      # inline synthetic refs; no corpus needed yet

# stage 2 adds, without reshaping the above:
meep/sources/{base.py, local_reader.py}
meep/tools/{find_attestations.py, propose_conjecture.py}
meep/agents/attestation_worker.py
examples/local_corpus/           # manifest.csv + texts/, mirrors atelier/examples/local_corpus
```

Built fresh, so the layout ATELIER already uses (package dir + sibling
`tests/` + root `demo.py`/`run_demo.py`) is adopted from day one — no
"ships under an earlier name, rename before stage 2" step, unlike what the
design doc's §11 describes for the (nonexistent) prior build.

---

## Architecture highlights (stage 1)

**Closed vocabulary.** `NodeType`, `EdgeType`, `NodeStatus`, `DatingRoute` as
`StrEnum`; one pydantic payload class per node type (`WitnessPayload` carries
a `Dating` record; `PassagePayload` carries `canonical_ref` + `locator`, no
`witness_ref` field — see below); `Authorship(author, at, action)` list on
every node/edge, appended to, never overwritten.

**Edge domain constraints**, straight from design doc §6's table, enforced
in `graph.py` before any SQL runs — e.g. `attests` only from `passage` to
`claim`/`conjecture`; `tests` only from `query` to `conjecture`.

**Two decisions that fix §11's own "known weak points" by building
correctly the first time, since there's no migration cost yet:**
- `part_of` (passage → witness) is a **first-class edge**, added to the
  vocabulary, not a JSON payload field. The design doc flags the payload-field
  version as a known weak point to fix in stage 2; there's no reason to build
  the weak version first when `independent_support()` needs the traversal on
  day one anyway.
- `contradicts` and `parallel_of` are **written as two rows** (both
  directions) from one logged event, fixing the "not symmetric on read" flaw
  the doc flags, at zero extra cost.

**The falsifiability gate (§7)**, enforced inside `attest()`:
a `claim` needs ≥1 inbound `attests` edge from a passage that is itself
`attested` or `accepted`; a `conjecture` needs ≥1 inbound `tests` edge —
`attests` edges never satisfy it, however many exist, which is what makes a
conjecture "smuggled in through the wrong function" permanently unattestable
by that route.

**The promotion ladder (§8)**: `propose_*` → `attest()` → `accept()` /
`reject()`, no rung skipping, `accept`/`reject`/`reopen` require
`authored_by == "researcher"`, `citable()` returns only `accepted` nodes.
Persistent rejection and identity convergence turn out to be the *same* code
path for source-derived nodes: re-proposing an existing `canonical_ref`
either appends a `converged` authorship record (any non-rejected status) or
raises (rejected status).

**`independent_support(node_id)`** — the 3-line demo output the design doc
calls the counter-argument to consensus-seeking: attesting count, distinct
witnesses (via `part_of`), and an `independent` flag that flips to `False`
the instant a `descends_from`/`parallel_of` edge is recorded between two
supporting witnesses, with `attesting_count` unchanged. Get this one right
before anything else in stage 1 — it's what gets shown first.

**Event log correctness — a deliberate fix to a named prior bug.** The
design doc's §11 notes a predecessor's `rebuild` wrote a stray replay log
because the constructor insisted on one. Structural fix, not a patch:
`EventLog.__init__` never truncates an existing file; replay is a separate
**pure module-level function** (`read_events`) that never instantiates an
`EventLog` at all, so `Graph.rebuild()`'s shadow graph is constructed with
`event_log=None` and is structurally incapable of writing a stray file.

**Single-writer discipline (§7 principle 7).** Non-blocking `fcntl.flock`
on a sidecar lock file, acquired on open, released on close or by the OS on
process death. Fails loudly and immediately on contention rather than
queueing — appropriate for a system that's supposed to demonstrate
discipline, not paper over its absence. Stage 1 tests only that the lock
exists (open twice, second one raises); the doc's own instruction — "write
the contention test before the fan-out" — stays deferred to stage 5, where
real concurrency shows up.

**One deliberate ladder exception**: `decision` nodes are written directly
at `status=accepted` with a single authorship record. A decision is
definitionally the researcher's already-authoritative word; subjecting it to
its own promotion ladder would be a regress.

---

## Testing strategy (stage 1)

One test per rule the design doc claims, split across `test_schemas.py` /
`test_eventlog.py` / `test_graph.py` (splitting design doc §11's single named
file along the four module boundaries — same coverage, easier to navigate
as the suite grows past ~22 tests). Directly required by §11's own list:
source-derived identity + author accumulation; edges never create missing
endpoints; every edge domain constraint (positive and negative); the
falsifiability gate including the wrong-function-smuggling case; the full
ladder with authority checks; persistent rejection blocking re-proposal;
`citable()` excluding everything but accepted; rebuild-from-log matching the
live projection exactly, **and** a regression test asserting rebuild does
not write a stray file; a refused write still leaving an honest log entry.
Plus, from the decisions above: both-directions materialization for
`contradicts`/`parallel_of`; the `independent_support()` flip on
`descends_from`/`parallel_of`; the single-writer lock check (explicitly not
a concurrency test).

---

## Build roadmap

| Stage | Deliverable | Status |
|---|---|---|
| 1 | Graph store, event log, vocabulary, ladder, rebuild | **To build** — spec exists (§11), code does not |
| 2 | Thin `search`/`fetch` source interface + local FTS5 reader; named tool layer; `find_attestations` worker | Not started; open decision — development corpus (§14) |
| 3 | Conjecture generation behind the falsifiability gate; persistent rejection in a live loop | Not started |
| 4 | `parallel_of`/`descends_from` from existing markup; contradiction surfacing; `independent_support` over real witnesses | Not started; open decision — does the corpus carry parallel markup already? (§14) |
| 5 | Real concurrency fan-out; researcher UI (graph view, accept/reject, provenance on click) | Not started |
| 6 | ATELIER integration: source interface becomes an adapter; cumulative-coverage policy | Not started |

Design doc's own cut order still applies if time runs short: **cut stage 5
before stage 3** — a small graph with a working falsifiability gate is the
contribution; a large swarm without one is the thing being critiqued.

**Open decisions this document does not resolve** (design doc §14,
unchanged): development corpus (public-domain/locally-held, small enough to
iterate — Michael's Buddhist material or a CBETA/Kanripo checkout are
candidates); corpus markup format, which determines how close stage 4 is
once stage 2 lands; chronology scheme (translation vs. composition vs.
recension date, coordinate with CWN.dia); division of labour across
rich/Tyler/Chunki for stages 2 and 4 (stage 3 probably isn't separable).
None of these block writing stage 1, since stage 1 needs no corpus at all.

---

## Verification

When stage 1 is implemented: `pytest -q` green, `demo.py` runs and prints
the `independent_support()` flip, and a manual rebuild check (delete the
sqlite file, re-run from the event log, diff against a saved snapshot) — the
same shape as the `test_rebuild_matches_live_after_full_workflow` test, just
run by hand once.
