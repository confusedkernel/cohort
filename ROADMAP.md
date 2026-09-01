# Roadmap: structure, tech stack, design ideology

## Scope revision

This is a conscious reversal of two `DESIGN.md` passages, not a drift.
`DESIGN.md`'s own standing rule is: *"when a rule here cannot be honoured,
say so and stop... The predecessor's central problem was documentation
describing guarantees the code did not provide."* So, said plainly:

- §9's anti-goal *"Agent count as a headline number. A scale claim, not a
  mechanism"* is **superseded**. More logical agents are now allowed, on the
  condition they demonstrate declared viewpoint diversity (distinct
  corpus/method scope per agent) — not because a bigger number is itself
  the claim.
- §4's *"Fan-out is not a headline... the discipline of the design is the
  interesting part, not the agent count"* is superseded for the same reason.
- §2 rule 1's *"Public-domain or locally-held material only"* is
  **clarified, not relaxed**. COHORT's confirmed development corpus is CBETA
  (`CBETA_電子佛典_xml_v061_20210710.zip`) — locally-held, but licensed
  CC BY-NC-SA-equivalent (non-commercial, attribution, share-alike, version,
  intact-header requirements), not public domain. Read disjunctively:
  locally-held material qualifies on its own, provided its real license
  terms are preserved through every derived artifact. This does not touch
  rule 2 ("claim no governance") — COHORT still makes no retention or
  rights-aware claims; it accepts a real corpus under real restrictions and
  is disciplined about carrying them. Corpus bytes stay out of the
  repository; only a local path (`CBETA_ARCHIVE_PATH`) is configured.

Everything else in `DESIGN.md` — all seven principles in §5, and every other
anti-goal in §9 — **survives untouched**; each addition below was checked
against all seven before being written. §6's "closed on purpose... adding a
type requires an argument" vocabulary discipline is being *exercised*, not
abandoned: every new node/edge type below carries its argument inline, same
as the existing vocabulary does.

---

## Status note

`DESIGN.md` §11 originally described stage 1 as already built, when in fact
nothing existed on disk under any name. That gap is closed: **stage 1 and
stage 2 are both now implemented** (see the build roadmap table below).
Stage 1's `schemas.py`/`errors.py`/`eventlog.py`/`graph.py` are built to the
§11 spec, with `pytest -q` green and `demo.py` printing the
`independent_support()` flip. Stage 2's source interface, local FTS5
reader, the named tools, and the attestation worker are built and tested. The
API round-trip this section once flagged as untested is no longer a gap: the
worker runs over OpenRouter, not the Anthropic SDK, and has completed real
calls many times over (see "Verification" below). The corpus used for stage
2's tests (`examples/local_corpus`) is still an illustrative fixture of
public-domain Tang poems; the real development corpus (CBETA v061) arrived
later and is used by the manual live scripts, not by the suite.

Decisions already made:
- The agent/LLM layer (stage 2's attestation worker, stage 3's conjecture
  generator) uses **no client library at all**: OpenRouter over stdlib
  `urllib.request`. This decision was originally recorded here as "the plain
  Anthropic Python SDK"; the conclusion it was protecting — not the Agent SDK,
  not a third-party framework — is unchanged, and the SDK itself turned out to
  be surplus to it.
- COHORT's source interface is shaped like ATELIER's `search`/`fetch`
  (`DESIGN.md` §2), and ATELIER's other conventions are the default for
  team consistency (same authors, same Sindia infrastructure track) —
  cited below as `atelier/...` paths.
- Stage 5's researcher UI (graph view, accept/reject, provenance on click)
  will be **Python-oriented with an optional web UI**: a FastAPI backend
  exposing a JSON API over `graph.py`'s read-only surface
  (`citable()`/`rejected()`/`independent_support()`/`assurance_for()`/
  `agent_report()`, etc.), consumed by a separate JS/React frontend. The
  core system's CLI/library usage must never require the UI to be
  installed or running — the same "optional" pattern as the `dev` extra in
  `pyproject.toml`. Deliberately kept minimal: no
  Postgres, no queue — FastAPI reads the same single SQLite file
  `graph.py` already owns. **Built (read-only), once stage 3 and stage 4's
  main halves were done** — the design doc's cut order ("cut stage 5 before
  stage 3") governs what to drop under time pressure, not what may be built
  next, and the condition it protects was satisfied. The concurrency detail
  above resolved differently than this paragraph first assumed: the UI does
  *not* run inside the process holding the write lock. It opens its own
  read-only connection via `Graph.open_read_only()`, which takes no lock at
  all, because WAL already makes concurrent readers safe and a reader has no
  business asking for a writer's lock. Accept/reject **is** built, behind
  `serve_ui.py --allow-writes`: each write takes the exclusive lock for one
  request and answers 409 if an agent run holds it, so it never blocks a run
  for longer than a request. An earlier note here predicted a writing UI would
  have to hold the lock for as long as a browser tab was open, which was simply
  wrong, and was the only thing that had been blocking it.

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
node/edge vocabulary; reimplementing ATELIER's governance inside COHORT;
claiming governance COHORT doesn't have; content-layer claims dressed as a
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
- **stage 2+: OpenRouter over stdlib `urllib.request`** — no client library
  and no extra to install (`cohort/agents/openrouter.py` says why). This
  replaced the plain `anthropic` SDK originally planned here, and with it the
  optional `agents` extra that plan implied: there is no such extra in
  `pyproject.toml`, because a dependency-free transport needs none. The
  reasoning that ruled out heavier frameworks still holds and still applies —
  no LangChain, no Agent SDK: the tool layer is already the constraint surface
  (Principle 4), so a framework would add machinery the design doesn't need.
- **stage 2+ local reader**: stdlib SQLite FTS5, reimplementing (not
  importing — COHORT stays standalone per §2) the character-unigram trick from
  `atelier/atelier/adapters/local_corpus_adapter.py`. FTS5's default
  tokenizer treats an unbroken CJK run as one token, so `MATCH "寂寞"`
  against a real sentence matches nothing; indexing space-separated
  characters and phrase-querying fixes this without a segmenter dependency.
  Directly relevant since the likely corpus (CBETA/Kanripo, per design doc
  §14) is Classical Chinese.
- **stage 5 (built): FastAPI** behind an optional `ui` extra, serving a JSON
  API over `graph.py`'s surface, plus **a separate JS/React frontend** for the
  graph view / accept-reject / provenance-on-click UI, and a corpus browser and
  agent-run launcher besides. Optional in the sense `dev` is: the core system
  never depends on it. No Postgres, no queue — one SQLite file. Reads open
  their own connection via `Graph.open_read_only()` and take no lock at all,
  rather than running inside the writer's process as first planned; writes
  (accept/reject/reopen) take the exclusive lock for one request each.

---

## Project structure

```
cohort/
├── pyproject.toml
├── README.md
├── ROADMAP.md                 # this document
├── cohort/
│   ├── __init__.py
│   ├── schemas.py              # closed vocabulary: nodes, edges, events, dating,
│   │                            # verification/assurance, agent identity
│   ├── errors.py                # one exception per rule
│   ├── eventlog.py               # append-only JSONL, never truncated
│   ├── graph.py                   # SQLite projection, the only writer
│   ├── sources/{base.py, local_reader.py}
│   ├── tools/{find_attestations.py, propose_conjecture.py}
│   └── agents/attestation_worker.py
├── tests/
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_eventlog.py
│   ├── test_graph.py
│   ├── test_local_reader.py
│   ├── test_tools.py
│   ├── test_attestation_worker.py   # mocked client — no live API round-trip
│   ├── test_verification.py         # verify()/assurance_for()
│   └── test_agents.py               # register_agent()/agent_report()
├── examples/local_corpus/            # manifest.csv + texts/ — a fixture, not the dev corpus
└── demo.py                      # inline synthetic refs; no corpus needed yet
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

## Architecture highlights (Scope revision axes)

**Observability envelope.** Eight new optional `Event` fields (`model_call_id`,
`model`, `provider`, `prompt_version`, `latency_ms`, `input_tokens`,
`output_tokens`, `cost_usd`), all defaulting to `None` so every event logged
before this addition replays identically. A new `"model_call"` event type,
non-mutating like `"refused"` — one API response can drive several tool
calls and several graph writes, so latency/cost live on their own event,
referenced by the writes it caused via `model_call_id` (pointing at that
event's `seq`, not a new id scheme). `Graph.log_model_call()` and
`summarize_model_calls()` (a pure log scan in `eventlog.py`, since
`model_call` events never touch the SQLite projection) are the two new
entry points. `AttestationWorker.run()` measures latency around every
`messages.create()` call and threads the resulting `model_call_id` through
`_dispatch()` into both tools.

**Verification and assurance.** A new `verification` node type and `verifies`
edge (verification → claim/conjecture/passage/witness), parallel to how
`decision` already records a researcher judgement without being evidential
content — born directly at `status=accepted`, same reasoning as `decision`.
`AssuranceLevel` (`A0_UNCHECKED` → `A4_HUMAN_APPROVED`) is a **computed
read** (`Graph.assurance_for()`, the max *passing* level across a node's
verification nodes), never a second mutable field — the graph stays a
projection. Five domain-appropriate `VerificationMethod`s
(`locator_resolution`, `exact_span`, `cross_edition_collation` — which
wraps `independent_support()` — `dating_route_confidence`,
`human_review`); deliberately no numerical/statistical/code/database
verifiers (no such claims exist here) and deliberately no
`MODEL_ENTAILMENT` — a second model's opinion is still another agent's
opinion, and admitting it as a formal verification method would smuggle
consensus-among-models back in through the side door, directly against §4's
thesis.

**Conjecture dossier.** `ConjecturePayload` gained four required fields
(`derivation`, `corpus_boundary`, `selection_risks`,
`alternative_explanations`), enforced by pydantic at proposal time — not a
new write-boundary rule. The falsifiability gate itself, `attest()`'s
conjecture branch, is **unchanged**: it still asks only for a `tests` edge.
A new `searched_for` edge (query → conjecture) records that a prior-art
search was actually run — required and executed by the `propose_conjecture`
**tool** (search-then-propose against the `Source`), not by `graph.py`.

**Agent identity.** A sidecar `agents` table (id, kind, corpus_scope,
method_label), not a graph node type — an agent's declared scope is
operational metadata about a writer, not evidence about the corpus
(principle 2), same footing as `node_authorship`/`edge_authorship`.
`register_agent()` is additive and idempotent (upsert on re-registration);
`authored_by` is **not** enforced as a foreign key against it, so every
existing ad hoc `authored_by` string keeps working unregistered.
`AttestationWorker` takes an optional `profile: AgentProfile`, folded into
its instructions alongside the rejection context — this is what "viewpoint
formation without persona theater" means concretely: diversity comes from
declared corpus/method scope, not a personality prompt over an identical
view of the whole corpus. `Graph.agent_report()` is a pure contribution-history
**count** (proposed/attested/accepted/rejected/discount-edges-contributed),
deliberately not a score — reputation *scoring* and the `asyncio` fan-out
needed for real multi-agent interleaving are explicitly deferred, not built
in this pass.

**Declined outright, not just deprioritized**: inter-agent social actions
("ask a question," "propose collaboration," "form/leave a research group")
need some channel for agents to address each other, which is principle 3
verbatim ("no agent-to-agent messaging, no shared transcript") — a direct
contradiction, not a stylistic mismatch. Most of that social-action
vocabulary already has a COHORT-native equivalent for free: `contradicts`
edges are "challenge"; re-adding an existing edge already accumulates
authorship via the convergence mechanism, which *is* "endorse"; `supersedes`
already exists unused in the vocabulary and is the natural fit for
"revise/retract," left for whenever it's actually needed.

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

**Scope-revision axes** (85 → 96 tests across this pass): `test_verification.py`
covers `verify()`'s ladder-bypass birth status, the ineligible-subject and
non-researcher refusals, `assurance_for()` ignoring failing/indeterminate
results and picking the max passing level, `citable()` excluding
verification nodes, and rebuild fidelity with `verify` events present.
`test_agents.py` covers registration, idempotent re-registration, the
unregistered-`authored_by`-still-works case, `agent_report()`'s counts
(including that rejection only shows on the researcher's own report, since
only the researcher may reject), and rebuild fidelity with `register_agent`
events present (the new `agents` table is now part of `_snapshot()`'s
comparison). `test_eventlog.py`/`test_graph.py`/`test_attestation_worker.py`
gained direct coverage that `model_call` events are non-mutating, that
`model_call_id` threads through to the write it caused, and that the
worker's declared profile and rejection context compose correctly in the
sent instructions.

---

## Build roadmap

| Stage | Deliverable | Status |
|---|---|---|
| 1 | Graph store, event log, vocabulary, ladder, rebuild | **Done** — `cohort/{schemas,errors,eventlog,graph}.py`, 47 tests, `demo.py` |
| 2 | Thin `search`/`fetch` source interface + local FTS5 reader; named tool layer; `find_attestations` worker | **Done, live-verified, now corpus-wide** — `cohort/sources/`, `cohort/tools/`, `cohort/agents/attestation_worker.py`. The CBETA archive is obtained and hash-verified, and `cohort/sources/cbeta_fts.py` indexes all 20,190 entries (15.28M citable spans, ~1.1 GB, built by `scripts/build_cbeta_index.py`), so `CbetaReader.search()` covers the real corpus rather than a hand-listed fixture. Searchable spans are exactly the citable ones, so every hit is fetchable by construction. Results are corpus-ordered, deliberately unranked — see `HANDOFF.md` |
| 3 | Conjecture generation behind the falsifiability gate; persistent rejection in a live loop | **Done, live-verified.** `Graph.rejected()` + `AttestationWorker._rejected_context()` make rejection hold for `claim`/`conjecture` even though they have no content-derived identity to block on mechanically (principle 5) |
| 4 | `parallel_of`/`descends_from` from existing markup; contradiction surfacing; `independent_support` over real witnesses | **Unblocked; `parallel_of` and collation halves done, live-verified.** `cohort/sources/cbeta_markup.py` parses `<cb:docNumber>` cross-references and `<app>` apparatus; `cohort/tools/link_parallels.py` writes `parallel_of` edges (asserted references only, and only to witnesses already in the graph); `cohort/tools/collate_editions.py` records `CROSS_EDITION_COLLATION` verifications. `scripts/run_stage4_demo.py` shows `independent_support` flipping on three real Heart Sutra translations, derived from the corpus rather than hand-added. Contradiction surfacing now has a producer: `cohort/tools/record_contradiction.py` writes `contradicts` edges with a mandatory stated reason (edges gained a `reason` column, migration 3), and it is registered in `AttestationWorker`. Still open: `descends_from` extraction — the markup asserts parallelism, not descent, so there is no corpus channel for it — and *automatic* contradiction detection across witnesses, which needs locus alignment COHORT does not have and does not claim. `link_parallels`/`collate_editions` are **now registered as agent tools** and have been called by a real model — neither takes a judgement as input (only a `witness_id`; the corpus supplies the content), which is what settled the question. See `HANDOFF.md` |
| 5 | Real concurrency fan-out; researcher UI (graph view, accept/reject, provenance on click) | Fan-out **done, live-verified**. Researcher UI **built** — read-only by default, with writes, corpus and runs each opt-in behind a separate flag — `cohort/ui/api.py` (FastAPI over `graph.py`'s reader surface) + `cohort/ui/frontend/` (React/Vite), both behind the optional `ui` extra; served by `scripts/serve_ui.py` against a graph seeded from the real archive. Serves while an agent run holds the write lock, via `Graph.open_read_only()`. Renders §10's requirements (status as a visual channel, discounting edges distinct from supporting ones, contradiction as visible as agreement, provenance on click). **Accept/reject is now built** (`--allow-writes`), which retires this row's earlier claim that a writing UI would have to hold the exclusive lock "for as long as a tab is open" — that was wrong. Each write takes the lock for one request and releases it; a run holding the lock yields a 409 with a stated reason, so single-writer discipline is unchanged rather than relaxed. The UI also reaches parity with the Python API on two further fronts: corpus browse/search (`--corpus`) and an agent-run launcher (`--allow-runs`) with a per-run spend cap the browser cannot raise. Live-verified end to end over HTTP. The "many agents" half is **now reachable from the UI**: a run is one or several agents, each with its own declared corpus scope and method, sharing one graph, one lock and one budget cap; live-verified with two concurrent agents. See `HANDOFF.md` |
| 6 | ATELIER integration: source interface becomes an adapter; cumulative-coverage policy | Not started |

Design doc's own cut order still applies if time runs short: **cut stage 5
before stage 3** — a small graph with a working falsifiability gate is the
contribution; a large swarm without one is the thing being critiqued.

**Scope-revision axes** (orthogonal to the stage sequence above — see
"Scope revision" at the top of this document):

| Axis | Status |
|---|---|
| Observability envelope | **Done** — `Event` fields, `log_model_call()`, `summarize_model_calls()`, threaded through the worker and both tools |
| Verification/assurance model | **Done** — `verify()`, `assurance_for()`, five domain-appropriate methods; `CROSS_EDITION_COLLATION` is `independent_support()` finally wired into a formal, queryable record (the same workstream as stage 4's "`independent_support` over real witnesses") |
| Conjecture dossier | **Done** — four required `ConjecturePayload` fields, `searched_for` edge, search-then-propose in the tool. The falsifiability gate itself is unchanged |
| Multi-agent society, steps 1-3 | **Done** — `agents` table, `register_agent()`, `AttestationWorker(profile=...)`, `agent_report()` (counts only) |
| Multi-agent society, step 4 (real concurrency) | **Done, live-verified** — `cohort/agents/swarm.py::run_swarm()`; `AttestationWorker.run_async()` is now the canonical loop, with `asyncio.to_thread` scoped only around the one blocking HTTP call so concurrent workers' graph writes can never interleave |
| Multi-agent society, step 5 (reputation scoring) | Still deferred, deliberately — concurrency didn't change the reasoning that kept it out: it's about what a score would reward, not when agents run |

**Open decisions this document does not resolve** (design doc §14):
chronology scheme (translation vs. composition vs. recension date,
coordinate with CWN.dia). The development-corpus question is resolved
(CBETA, see "Scope revision"), the archive has been obtained, and the corpus
markup-format question is now answered empirically — CBETA's TEI does carry
usable parallel cross-references (`<cb:docNumber>`) and pervasive variant
apparatus (`<app>`), both of which stage 4 now reads. See `HANDOFF.md` for
the current concrete state and next steps.

---

## Verification

Stage 1's original check — `pytest -q` green, `demo.py` printing the
`independent_support()` flip, and a manual rebuild diff — is done and has
stayed green through every stage since (260 tests). `demo.py` still runs with
no corpus and no API key.

What the live scripts have additionally proven, each run by hand and never
automated: a real OpenRouter call (`smoke_openrouter.py`); two *concurrent*
real agents writing to one graph (`run_swarm_demo.py`); attestation against
the real hash-verified CBETA archive (`run_cbeta_demo.py`); the stage-4
`parallel_of` flip on three real Heart Sutra translations
(`run_stage4_demo.py`); a conjecture through the falsifiability gate with a
real prior-art search (`run_conjecture_demo.py`, $0.004); and an agent run
started from the browser (`$0.00236`, 4 calls) that used `propose_claim` and
`find_attestations` with **zero** invented-node-id refusals — the five such
refusals in the earlier conjecture run were the gap `propose_claim` closed.

Rebuild fidelity and payload integrity are re-checked after each live run, not
assumed: the last one replayed 81 events to 37 nodes / 43 edges matching the
live projection, with 0 mismatched payload hashes.
