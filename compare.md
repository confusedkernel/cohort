# COHORT and Epistemic Swarm

A comparison of two systems built in the same lab, from the same brief, toward
the same sentence — and the different instruments that came out.

Compared: `~/cohort` (this repository) and `~/epistemic-swarm`
(`lopentu/epistemic-swarm`), both as of **2026-09-02**. Every number below was
read off the two working trees, not estimated. §10 adds a third system,
`graph-fact-check`, read off its tree the same way.

> **Recommendations for COHORT implemented in response to this comparison:**
> model-family disjointness (§8.1), edge retraction (§8.2), an output-token
> ceiling (§10), and — the sharpest of them — a **reviewer role** with the
> author-is-not-reviewer rule enforced at the write boundary (§10). They are
> marked below. The rest still stand.

---

## 1. They are siblings, not rivals

These are not two teams who happened to converge. They share an ancestor
document, and the evidence is specific:

| Shared | Both projects |
|---|---|
| Governing phrase | *"Evidential pluralism made auditable"* — verbatim in both |
| Corpus | `CBETA_電子佛典_xml_v061_20210710.zip` |
| Archive SHA-256 | `90a663f2…7158f2` — the same constant in both codebases |
| A specific warning | Do **not** substitute the convenient `/mnt/md0/…/Bookcase/CBETA/XML` tree; a checked document differs from the archive copy |
| Licence stance | CC BY-NC-SA-equivalent, non-commercial/attribution/share-alike/version/intact-header preserved through derived artifacts; corpus bytes never committed |
| Assurance ladder | `A0_UNCHECKED` … `A*_HUMAN_APPROVED`, described as cumulative, explicitly *not* a confidence score |
| Falsifiability dossier | Derivation, corpus boundary, selection risks, alternative explanations, prior art, discriminating test |
| Contribution claim | 工具層 / methodological infrastructure, **not** an argument about textual history |
| Transport | OpenRouter, `z-ai/glm-5.3-flash` |
| Refused anti-goal | Consensus-seeking; agreement is never evidence of truth |

Neither repository references the other — no mention of ATELIER, Sindia or
COHORT appears in Epistemic Swarm, and no mention of Epistemic Swarm appears
here. They are independent implementations of one brief.

**So the interesting question is not who is right. It is what each one built
when the shared brief ran out.**

---

## 2. The sharpest difference: what "independence" means

Both projects begin from *agreement is not truth*. They then answer a different
question about **whose** agreement is suspect.

**Epistemic Swarm guards the independence of the readers.** Its reviewers must
come from a *model family disjoint from every lens model*. The worry is shared
training priors, prompt convergence, redundancy: two models agreeing may be one
model twice. This is enforced at the configuration boundary — a roster with
overlapping families is refused.

**COHORT guards the independence of the read.** Its central mechanism,
`independent_support()`, flips a claim's `independent` flag to `False` the
moment a `descends_from` or `parallel_of` edge links two of its attesting
*witnesses*. The worry is shared manuscript descent: two witnesses agreeing may
be one transmission event seen twice. This is the project's whole thesis, and
`demo.py` exists to show it in three lines of output.

Neither has the other's mechanism:

- Epistemic Swarm has **no** `descends_from`, no `parallel_of`, no
  stemmatic relation of any kind. The string "independen" appears in its
  documentation only as *independent reviewer models*. Its own external
  reviewer noticed the consequence: *"No commentarial, translation-historical,
  or stemmatic content appears, despite the charters."*
- COHORT had **no** model-family disjointness rule when this was written: its
  swarm ran several agents on one model, so two agents agreeing might have been
  exactly the redundancy Epistemic Swarm refuses. **Fixed** —
  `cohort/agents/roster.py` now refuses a roster whose agents share a provider
  prefix, at the run boundary and before any request. The heuristic is weaker
  than Epistemic Swarm's explicit family lists and says so.

These are complementary halves of one problem, and each project has implemented
the half the other left open. That is the single most useful finding in this
comparison.

It is worth being precise about what Epistemic Swarm *does* do here, because it
is close: `collation-worker.ts` deterministically extracts the TEI critical
apparatus — the Taishō base reading and each 宋/元/明 witness variant — and
records it as immutable evidence, with an empty collation counted as the honest
finding *"no witness varies here."* COHORT's `collate_editions` reads the same
markup. The difference is what happens next. Epistemic Swarm records witness
variation **as evidence for a human to read**. COHORT converts it into a graph
relation **that mechanically discounts support**. One surfaces the fact; the
other makes the fact change the arithmetic.

---

## 3. Where they agree, in code rather than in prose

Both enforce these at a boundary rather than requesting them in a prompt:

- **No ranking, merging, or averaging** of readings, anywhere.
- **Nothing model-written is true.** Both keep model output in a
  proposed/unaccepted state by construction.
- **Every claim must be tied to source bytes**, checked deterministically —
  Epistemic Swarm locates a verbatim quote in the TEI base text and pins byte
  offsets; COHORT's `verify_exact_span` re-fetches and re-matches, recording
  `A2_EXACT_SPAN_MATCHED`.
- **Append-only ground truth, never overwritten.**
- **Every model call is recorded**, including failed and refused ones, with
  cost.
- **Hypotheses/conjectures need a falsifiability dossier**, refused without it.
- **Spend is capped in code** before the call, not reported after.
- **Bind to loopback deliberately**, because the corpus is licence-restricted.

The agreement is close enough to be worth stating plainly: on ideology, these
two projects are the same project.

---

## 4. Where they diverge

### 4.1 Who the researcher is, and what they do

| | COHORT | Epistemic Swarm |
|---|---|---|
| Researcher's central act | **Accept** — promote to citable | **Correct / retract** — acceptance is deliberately withheld |
| Promotion ladder | `proposed → attested → accepted`, no rung skipped; `rejected` persists and blocks re-proposal | 8 claim states (`DRAFT`…`RETRACTED`); in practice claims stay at `EVIDENCE_ATTACHED` |
| Is acceptance implemented? | **Yes**, live | **No.** `researcherActionNames` is review / correct / retract; even a human review event carries a literal `acceptsClaim: false` |
| Can the researcher act from the UI? | **Yes** — accept, reject, reopen, attest | **No.** The workbench is GET-only; researcher actions exist in the library but are not wired to any interface |

This is a real philosophical split, not just a schedule difference. Epistemic
Swarm treats machine-proposed acceptance as dangerous enough to leave
unimplemented, and makes *withholding* the safe default. COHORT treats the
researcher's signature as the point of the whole ladder — "only accepted nodes
may be cited or used as premises by other agents" — and so had to build it.

Each position has a cost. Epistemic Swarm's claims can never become citable, so
the downstream half of its own epistemic policy (synthesis over accepted claim
packets) cannot yet run. COHORT's accept button exists and can be pressed, which
means its safety rests on the ladder's preconditions actually being right.

### 4.2 Versioning, correction, retraction

**Epistemic Swarm is substantially ahead here.** Claims are versioned; a
correction appends a new version with a typed `SUPERSEDES` or `RETRACTS` edge;
version ordering makes lineage acyclic by construction; history tables reject
`UPDATE`, `DELETE` and `TRUNCATE` at the database level, and PostgreSQL
recomputes artifact and excerpt SHA-256 from stored bytes rather than trusting
a declared hash.

COHORT has `supersedes` in its vocabulary and a `reopen` action. **Edge
retraction is now built** (migration 4): the researcher may withdraw an edge
with a stated reason, it persists against redrawing by a tool, nothing is
deleted, and `independent_support()` stops counting it — so withdrawing a wrong
`parallel_of` restores the support it was suppressing without changing the
evidence count. **Claim versioning and in-place correction remain absent**, and
Epistemic Swarm is still ahead here: a COHORT claim can be rejected and
reopened, but not revised into a new version with a typed lineage edge.

### 4.3 Roles versus tools

**Epistemic Swarm structures agents by role.** Three kinds, with different
inputs and different authority:

- **Lenses** (≤16) get a *methodological stance* and the raw spans, and propose
  claims plus one interpretation. Charters containing consensus language
  ("agree", "converge", "reconcile") are **refused at the configuration
  boundary** — a nice piece of enforcement.
- **Reviewers** (≤8), from disjoint model families, re-derive quoted spans and
  record entailment judgments as *evidence, never proof*.
- **Proposers** (≤4) read the *admitted claims*, not the raw spans, and offer
  competing hypotheses.

The separation is epistemic: a proposer that cannot see the raw text cannot
quietly re-derive a claim it likes, and a reviewer that shares a lens's model
family cannot independently check it.

**COHORT structures agents by tool.** One worker kind with six named,
schema-validated, individually-refusable tools. Diversity comes from a declared
`corpus_scope` and `method_label` per agent rather than from a role. There is no
separate reviewer: verification is a tool any worker may call, and no rule stops
an agent from verifying its own claim.

Epistemic Swarm's design is stronger on *who checks whom*. COHORT's is stronger
on *what a write may be* — every write goes through a function that can refuse
it, and a refusal is recorded as output.

### 4.4 Scale, and what it costs to run

| | COHORT | Epistemic Swarm |
|---|---|---|
| Concurrency model | `asyncio` in one process, one shared `Graph`, one writer lock | `pg-boss` durable queue, multiple worker processes, leases and retries |
| Max agents | 4 (UI cap) | 28 executions (16 lenses / 8 reviewers / 4 proposers) |
| Largest measured run | 2 agents, 16 calls, 62.8 s, **$0.00336** | 28 executions, 92,389 tokens, 680 s, **$0.0203** |
| Scaling evidence | one live 2-agent run | a **four-point scaling study** (4 / 8 / 15 / 28 executions) with zero infrastructure failures |
| To run it at all | `pip install`, then a file | PostgreSQL 15+, `npm run db:migrate`, a worker process, a dispatch pass, then the run |

Epistemic Swarm has done the work COHORT has not: it has actually measured what
happens as the swarm grows, and published the table. COHORT's "many agents"
claim rests on one two-agent run.

The cost is operational weight. COHORT runs from a single file with one runtime
dependency; Epistemic Swarm needs a database, a queue and a multi-step
provisioning sequence before a single model call happens. For a PNC demo on
someone else's laptop that difference is not cosmetic.

### 4.5 Reach beyond the corpus

**Epistemic Swarm has a paper-acquisition subsystem** COHORT has nothing
comparable to: immutable acquisition authority in PostgreSQL, append-only
attempt history, a content-addressed local blob store, URL policy (HTTPS,
exact-host, credential-free, no query/fragment), and the rule that *a cache hit
is not evidence* — admission must independently re-copy and re-hash the bytes.

Its hypotheses also require a **recorded prior-art web search**. COHORT's
`propose_conjecture` requires a prior-art query too, but runs it **against the
corpus only** — so COHORT cannot tell you whether a conjecture is already known
to the literature. Epistemic Swarm's own reviewer flagged that even its version
is insufficient (prior-art artifacts came back `MODEL_RECALL_UNVERIFIED`), which
is a warning for both.

### 4.6 Governance

COHORT states flatly that it has **no** access-governance layer — no policy
file, no allowlist, no caps, no retention, no deletion verification — because
that is ATELIER's job and ATELIER is not connected. Its source interface is
shaped like ATELIER's adapter so integration is one class later.

Epistemic Swarm has no ATELIER to defer to, and instead carries its own
**open-source boundary**: every authoritative component must be self-hostable,
proprietary APIs may appear only behind optional adapters and may never own
canonical state, and OpenRouter is explicitly a temporary transport that must
be swappable for local inference on the DGX Station.

That is a commitment COHORT has never made and probably should consider, since
it uses OpenRouter as its only model path.

---

## 5. Implementation, side by side

| | COHORT | Epistemic Swarm |
|---|---|---|
| Language | Python 3.11+ | TypeScript / Node 22 |
| Runtime dependencies | **1** (`pydantic`); `fastapi`+`uvicorn` behind an optional extra | `fastify`, `pg`, `pg-boss`, `yauzl`, `zod`, `pi-coding-agent` |
| Store | SQLite projection + append-only JSONL log | PostgreSQL, append-only ledger with DB-level immutability triggers |
| Ground truth | The JSONL event log; SQLite is rebuildable from it and a test asserts the diff | The PostgreSQL ledger itself |
| Migrations | 3 | 9 |
| Concurrency safety | exclusive non-blocking `fcntl.flock`, WAL for readers | queue leases, transactions, `exclusive` queue for the CBETA worker |
| Model transport | stdlib `urllib` — no client library | `openrouter.ts` with strict boundaries |
| Source LOC | 6,336 package + 3,291 frontend | 19,993 `src/` |
| Test LOC / count | 4,469 / **295 tests** | 30,988 / 47 modules, ~572 cases (plus Postgres + Playwright suites) |
| Front end | React + Vite SPA; **read/write** | Server-rendered HTML + one vanilla JS file; **read-only** |
| CLI | `cohort`, 16 commands, parity with the web UI **enforced by a test** | 13 npm scripts, mostly operational stages |
| Lint / format | none configured, by house rule | eslint, prettier, knip dead-code, ruff + ty for Python |

Two implementation choices worth calling out in each direction.

**Epistemic Swarm's are stronger on defence in depth.** Immutability is enforced
by database triggers, not only by application discipline; hashes are recomputed
by PostgreSQL from stored bytes; a CI pipeline runs typecheck, format,
dead-code and browser tests. COHORT relies on one process holding one lock and
on tests to catch drift.

**COHORT's are stronger on portability and on the log being primary.** Its
ground truth is a text file you can read with `cat`, and `rebuild()` proves the
database is a faithful projection of it — a property Epistemic Swarm does not
need because its ledger *is* the database, but also cannot offer.

---

## 6. Feature matrix

| Capability | COHORT | Epistemic Swarm |
|---|---|---|
| Byte-exact source pinning | ✅ hash-verified archive, `source_ref` re-fetch | ✅ hash-pinned excerpts, byte ranges, re-verified on read |
| Verbatim quote required per claim | ⚠️ passages carry excerpts; no verbatim-quote gate at claim admission | ✅ deterministic quote location, fabricated quote rejected |
| Full-corpus search index | ✅ FTS5 over 15.28M citable spans, every hit fetchable by construction | ⚠️ researcher names spans; no corpus-wide search |
| Deterministic pattern counting | ❌ | ✅ census worker; "models are never used as counters" |
| Critical-apparatus collation | ✅ `collate_editions`, joint sigla never split | ✅ `collation-worker`, empty collation is a finding |
| **Shared-descent discounting** | ✅ **`independent_support()`** | ❌ |
| **Disjoint reviewer model families** | ❌ | ✅ **enforced at config** |
| Independent entailment review | ❌ | ✅ recorded as evidence, never proof |
| Falsifiability gate | ✅ refused without a `tests` edge | ✅ refused without prediction/test/counterargument |
| Prior-art search | ⚠️ corpus only | ✅ web, but `MODEL_RECALL_UNVERIFIED` |
| Contradiction as first-class | ✅ `contradicts` edge with mandatory reason | ✅ `opposes` links on interpretations |
| Claim versioning / supersession | ❌ | ✅ |
| Retraction | ❌ (nodes reject; edges permanent) | ✅ typed `RETRACTS` |
| Researcher accept | ✅ live, from UI and CLI | ❌ deliberately unimplemented |
| Researcher correct / retract | ⚠️ reject + reopen only | ✅ |
| Refusals as scholarly output | ✅ read from the log, surfaced in UI and CLI | ✅ failed and rejected calls recorded in the ledger |
| Rebuild-and-diff integrity proof | ✅ | ➖ n/a (ledger is the store) |
| Payload-hash tamper check | ✅ `verify_integrity()` | ✅ DB-recomputed hashes |
| Durable queue / retries | ❌ | ✅ `pg-boss` |
| Measured scaling study | ❌ | ✅ four sizes, published table |
| Paper acquisition | ❌ | ✅ |
| Web UI writes | ✅ | ❌ read-only |
| CLI/UI parity, enforced | ✅ by test | ❌ |
| Self-hosting commitment | ❌ OpenRouter only | ✅ explicit policy |
| Access governance | ❌ deferred to ATELIER, stated plainly | ❌ not addressed |

---

## 7. Are we working toward the same direction?

**At the level of the thesis: yes, almost exactly.** Both refuse consensus,
both keep incompatible readings, both bind claims to source bytes, both put a
falsifiability gate in front of novelty, both record refusals, both insist the
human decides. If either project's ideology section were dropped into the
other's repository, almost nothing would need changing.

**At the level of the instrument: no, and productively so.** They have
specialised in opposite directions from the same starting point.

- **COHORT is an argument with a demo attached.** It is small, portable and
  built around one claim — that corroboration weighting is invalid for
  transmitted corpora — with a mechanism that makes the claim operational and a
  three-line demo that shows it. Its risk is that the machinery around the
  argument (scale, versioning, reviewer independence) is thinner than the
  argument deserves.
- **Epistemic Swarm is an instrument with an argument attached.** It is a
  production-shaped research platform with durable queues, immutability
  triggers, a measured scaling study and external review. Its risk is the one
  its own reviewer named: the epistemics are impeccable and the *philology* is
  undergraduate, because nothing in it models transmission.

The honest summary is that **COHORT has the sharper idea and Epistemic Swarm
has the better instrument**, and both statements are true at once.

---

## 8. What each should take from the other

**COHORT should take from Epistemic Swarm:**

1. ~~**Reviewer-model-family disjointness.**~~ **Done, 2026-09-02.** The
   criticism was that COHORT ran several agents on one model and treated their
   outputs as distinct voices — its own error, committed against model priors
   instead of manuscripts. `cohort/agents/roster.py` now refuses such a roster
   at the run boundary; the model is recorded on each agent's profile; and
   `OPENROUTER_MODELS` supplies the pool. Family is the provider prefix, which
   is a floor on independence rather than a proof of one.
2. ~~**Edge retraction.**~~ **Done, 2026-09-02** (migration 4). A wrong
   `parallel_of` no longer suppresses real support permanently. **Claim
   versioning is still outstanding** — corrections here mean reject-and-reopen,
   not a new version with typed lineage.
3. **A measured scaling study.** One table at four sizes would replace an
   assertion with arithmetic — the house rule, applied to itself.
4. **A self-hosting position.** OpenRouter is currently COHORT's only path.
5. **Deterministic counting before interpretation.** The census idea — count
   byte-exactly, hand the agent the counts, let it interpret the exceptions — is
   directly applicable and would let COHORT's agents reason over a whole juan
   without trusting a model to count.

**Epistemic Swarm should take from COHORT:**

1. **A shared-descent relation with teeth.** It already extracts witness
   variation deterministically; one `descends_from` / `parallel_of` relation and
   an independence computation would turn that evidence into a correction, and
   would answer its reviewer's "no stemmatic content" objection at the level of
   mechanism rather than prompt.
2. **A researcher who can act from the interface.** The workbench is GET-only
   and the action registry is unreachable from it.
3. **Rebuild-and-diff.** Its ledger is its store, so it cannot prove a
   projection is faithful — but it could prove its projections are.
4. **Enforced CLI/UI capability parity.** Six sequenced shell commands with long
   environment-variable payloads is a real barrier for the PNC audience.

---

## 9. One line each

**COHORT**: a small, dependency-light evidence graph whose write boundary makes
one philological argument operational — that agreement between related witnesses
is not corroboration — and whose refusals are part of its output.

**Epistemic Swarm**: a self-hostable, queue-durable research instrument where
many models read the same pinned bytes under separated roles, everything is
recorded immutably, and the machine is never allowed to accept anything.

They are the same project's two halves, and the strongest version of either
would borrow the other's.

---

## 10. A third system, and a three-way reading

**Added 2026-09-02; revised the same day when the repository was opened.** A
labmate who has built a *third* implementation supplied their own comparison of
all three. It is reproduced and answered here because it makes a point neither
of the two-way sections above could: the projects are not slower and faster
versions of one thing, they optimise different quantities.

### The caveat this section opened with, and what happened to it

This section first said, at length, that the third system was private, that its
whole column was *attested-by-its-author* rather than verified, and that a
document about independence should say so.

**That is no longer the case.** The repository was cloned to
`~/graph-fact-check` and read: 11 commits, HEAD `7c39d58`, ~2,500 lines of
stdlib-only Python across 10 modules plus ~800 lines of design docs, with one
run's artifacts committed under `out/attribution/`. Its column is now on the
same footing as the other two — read off a working tree.

The original caveat is recorded rather than deleted because the change of
footing is the interesting part: **its author's self-report survived the check.**
Everything in their table that can be verified against the tree, is. That is
worth more than the caveat was.

### Their table, as given

| Axis | Epistemic Swarm | COHORT | Third system |
|---|---|---|---|
| What it optimises | auditable *instrument* throughput and integrity | the *discipline* (independence, refusals) as running code | *philological correctness* on a real question |
| Headline result | plurality scales linearly (13 distinct theses at max), 0 infra failures over 55 execs; a falsifiable whole-juan test gave a split verdict, refutation byte-pinned | the 3-line demo: support stays 2 while independence flips false on a `parallel_of` edge; budget hard-stop; FTS latency | verdicts match scholarship (T1492/T2027/T0091/T0092 misattributed); held-out test SUPPORTED; prior-art collapse 6 scholars → 2 sources = RELAYED |
| Model diversity | 4 families — genuine cross-family review | mostly single-model attestation workers; no cross-model reviewer | 2 families (GLM worker + Llama verifier) |
| Scale actually run | up to 28 execs, queue-dispatched | 1–2 agents, demo-scale | 93 calls, 42-agent fan-out |
| Binding constraint | "model capability, not the epistemic machinery" | still demo corpus / demo scale | verify cap (48) leaves ~edges unchecked; no wall-time metering |

Their net: *"es and ours are the only two that have run something at
non-trivial scale… cohort is architecturally the cleanest statement of the
discipline but is still demo-scale (~$0.003/run, 1–2 agents), so it has no
throughput/accuracy numbers to compare yet."*

### What the tree confirms

| Their claim | In the tree |
|---|---|
| 2 model families, worker ≠ verifier | `attribution.py:555` — worker `z-ai/glm-5.3-flash`, verifier `meta-llama/llama-3.3-70b-instruct`, separate clients, split enforced by construction |
| verdicts match scholarship | `out/attribution/report.md` — per-text verdicts; T1492/T2027/T0091/T0092 likely-misattributed, T1470/T0109/T0112 escalated as doubtful rather than averaged |
| held-out prospective test | `hypothesize_and_test()`, run over the second half of a target not used to form the hypothesis |
| prior-art collapse over the literature | `priorart.py` — `harvest()` keeps only URL-backed citations, `collapse()` counts named origins *and* distinct web hosts, flags relay |
| 93 calls, 42-agent fan-out | `N_SCOUTS = 24`, 18 assessors, `MAX_VERIFY = 48`, `ThreadPoolExecutor(max_workers=16)` |
| verify cap leaves edges unchecked | `verify()` slices `worker_edges[:self.max_verify]` and reports `capped` — the truncation is recorded, not hidden |
| no wall-time metering | true at run level; `_fold_usage` folds token counts only |
| stdlib-only | confirmed — no third-party import anywhere except `atelier.analysis.graph`, and that only inside the subprocess the ATELIER bridge shells out to |

Their read of **COHORT** also checks out where it is checkable: `confusedkernel/meep`
and `confusedkernel/cohort` are the same history, and COHORT's README does say
ATELIER integration "has not happened" ([README.md](README.md), "Access
governance is a separate system, and it is not connected"). Their
framing that all three descend from one graph-native-swarm brief is right about
COHORT too — [docs/design.md](docs/design.md) §4 is written as a response to it.

One small internal discrepancy: the large run is **533,344 tokens** in their
comparison table and **549k** in their `ROADMAP.md`; cost is `~$0.10–0.15 (est.)`
in both. The estimate is a consequence of implementation, not of care —
OpenRouter returns `usage.cost` on every response and `_fold_usage` folds only
the three token counts, so there is no exact figure to report.

### Two corrections, and one stale row

**"Mostly single-model attestation workers; no cross-model reviewer"** was
entirely true when written and is the most useful sentence in the table. Both
halves have since been answered, in that order and for the reasons this
comparison gave:

- A run whose agents share a model family is **refused at the boundary**
  (§8.1, 2026-09-02).
- There is now a **reviewer role** (`ReviewWorker`), and `Graph.attest()`
  refuses a claim whose author is the attester, or whose author shares the
  attester's model family. See the section below — the design took some care,
  because the obvious implementation would have contradicted the project's own
  argument.

**"Still demo corpus"** is not right, and the distinction matters for what the
demo-scale criticism actually means. The corpus is the **real hash-verified
CBETA v061 archive**, with a full-corpus FTS index over **15.28M citable spans
across all 20,190 entries**, where every hit is fetchable by construction. What
is demo-scale is the **run**, not the corpus: 1–2 agents over a small question.
Real corpus, small run.

**Stale, and superseded by their own newer document:** the earlier
`BUDDHIST_ATTRIBUTION_PIPELINE.md` §1 table (dated 2026-08-31, marked
design-only) lists COHORT as "Anthropic SDK", "Stage-1 core done; single worker;
LLM mocked". COHORT has no Anthropic dependency — it talks to OpenRouter over
stdlib `urllib` for the same reason their `client.py` does. Their
`SIBLING_SYSTEMS_COMPARISON.md` already replaces that row; noted only so a
reader of the older file doesn't take it as current.

### The difference the table exposes but does not name

Look down the first row rather than across it. Two of these projects claim a
**methodological** contribution and one claims a **content** one.

Epistemic Swarm and COHORT both state, in their own docs, that the contribution
is 工具層 / infrastructural and explicitly *not* an argument about textual
history. COHORT's design doc lists "content-layer claims" among its anti-goals
in as many words: *"Do not ship an argument about textual history dressed as a
demo."*

The third system's headline result is a set of **verdicts about textual
history** — which attributions are wrong, which held-out test was supported.
Reading the repository settles this rather than inferring it: the deliverable is
`out/attribution/report.md`, and it is a philological argument with per-text
verdicts, an eigen-word fingerprint table, and an escalated doubtful tier. It is
doing, deliberately and with a verifier, the thing COHORT rules out for itself.

That is not a criticism of it. It is the reason the three "don't share a
yardstick", stated more precisely than throughput-versus-discipline: **two are
infrastructure papers and one is a findings paper.** An infrastructure paper is
judged on whether the machinery refuses the right things; a findings paper is
judged on whether the findings are right. Scale and accuracy numbers are the
correct yardstick for the third and a category error for the first two — and
"cleanest statement of the discipline but no accuracy numbers" is only a
weakness if COHORT were trying to be the third kind of paper.

Worth stating plainly before PNC, since all three may present.

### What reading the code adds to their table

Four things it has that the table does not claim, and that COHORT should want:

1. **Boilerplate is excluded from provenance collapse.** `CbetaCorpus.is_boilerplate()`
   flags colophons and stock openings, and `checks()` unions witnesses only on
   `not d["boilerplate"]` descent links — 100 of 146 shared-passage links in
   their run were excluded on this ground. This is the sharpest borrowable idea
   in the repository and COHORT has no equivalent: `independent_support()` flips
   `independent` to `False` on *any* `descends_from`/`parallel_of` edge, with no
   notion that a shared *formulaic* passage is not evidence of descent. An agent
   drawing `parallel_of` from a stock opening would make COHORT understate
   independence, and nothing would catch it. **Now on the open-gaps list.**
2. **A deterministic evidence table the models may only cite from.**
   `build_evidence()` computes Burrows's Delta, eigen coverage, register ratios
   and genre baselines mechanically; a worker's claim is dropped unless it cites
   one of those ids, and fabricated cites are filtered
   (`attribution.py:387`). This is Epistemic Swarm's census worker arrived at
   independently — **two of three siblings now measure first and let models
   interpret**, which strengthens §8's fourth recommendation considerably.
   COHORT's tools return spans and compute nothing.
3. **Impostor baselines per genre.** `genre_baselines()` computes what coverage
   a *known-other-author* text of the same genre reaches on the fingerprint, so
   a 0/38 in a genre the fingerprint doesn't cover is reported as *not
   discriminating* instead of as evidence of misattribution. A guard against
   reading an instrument's blind spot as a finding — and the kind of move
   neither sibling has anywhere.
4. **Quantitative stylometry as reason-for-being.** Burrows's Delta over
   function words, eigen-word discovery verified rare canon-wide (df ≤ 80),
   char-trigram similarity. Confirmed absent from both siblings, which are
   census/collation/interpretation systems. Their claim to be the only one doing
   authorship distance is correct.

And four gaps the tree shows, offered in the same spirit their document offered
COHORT's — most of which their own docs already concede:

5. **No tests.** No test directory, no `pyproject.toml`, no runner, no
   assertion-bearing module anywhere in the tree. Epistemic Swarm gates on 600+
   hermetic tests, COHORT on 329. The three-way spread on this axis is wider
   than any other.
6. **No persistence.** `out/attribution/{graph,report,html}.json|md` is
   overwritten per run: no event log, no replay, no record of what was refused
   or dropped. Their own comparison lists this as something they "lack
   entirely", and it is the axis COHORT is built on.
7. **No human gate, though their own design requires one.**
   `BUDDHIST_ATTRIBUTION_PIPELINE.md` §4 step 5 T3 calls a human `accept` before
   citable "non-negotiable" for an attribution result — *"no auto-published
   re-attribution of a canonical text."* Nothing in the tree implements it: a
   grep for `accept` / `citable` / `human` across `swarm/` returns one unrelated
   string in a prompt. `report.md` publishes machine-only verdicts on canonical
   attributions. This is the one place where the findings-paper framing raises
   the stakes rather than lowering them, and it is their own stated requirement,
   unbuilt.
8. **`verify_span()` is defined and never called.** The T1 mechanical span
   re-check from the same design section — *"a claim whose span doesn't verify
   is rejected before any model sees it"* — is not wired. Grounding is enforced
   differently and genuinely: workers may only cite ids from the deterministic
   evidence table, which is a real constraint. But the guarantee is *"cites a
   measured evidence item"*, not *"quote re-verified against the bytes"*, which
   is what Epistemic Swarm re-checks at review time and what COHORT's
   `verify_exact_span` does on re-fetch.

One further one-line fix available to them: `client.py:62` already returns
`latency` per call and `_fold_usage` drops it. The wall-clock gap their own
table names as a binding constraint is a fold away from closed.

### The thing they have that COHORT most visibly lacks

Their **prior-art collapse — 6 scholars → 2 web sources = RELAYED** — is
COHORT's own thesis applied to *secondary* literature: six citations that look
like six independent authorities collapse to two evidentiary origins, so a
hypothesis that looked novel is correctly self-labelled *rediscovered*. Reading
`priorart.py` makes it more impressive than the table does — it keeps only
URL-backed citations and collapses along two axes at once, named scholarly
origin and distinct host.

COHORT models exactly this for witnesses and does nothing at all for the
scholarship that cites them: its `propose_conjecture` prior-art search runs
against the corpus only (§4.5). They also have the live ATELIER bridge
(`atelier_bridge.py` shells into ATELIER's own venv and runs its `build_graph`
for a period-aware second opinion), the integration COHORT defers to stage 6.

### What COHORT took from this

Their cost note — *"cap output tokens and meter wall-clock per run; we're paying
~1.7× their tokens/call partly because nothing bounds the reasoning model's
output"* — was addressed to their own pipeline, but half of it applied here.

- **Wall-clock and token/cost metering already existed.** Per model call
  (`latency_ms`, input/output tokens, cost) and per run (`elapsed_s`), read back
  from the event log rather than a running tally: the demo graph's log totals
  21 calls, 241,266 ms, 54,036 tokens, $0.00597.
- **Nothing capped output tokens.** Now `DEFAULT_MAX_OUTPUT_TOKENS = 2800`,
  sent on every request, liftable only by passing `None` deliberately. This is
  a cost bound, not a correctness one — `budget.py` remains the hard stop; the
  cap stops one call consuming an unreasonable share of it.

### The reviewer, and why it is not a second opinion

The criticism was right and it is now built. How it is built is the part worth
recording, because the obvious reading of "add a cross-model reviewer" would
have broken something this document spends §2 defending.

Both siblings' reviewers are, in part, entailment judges: a second model reads
the claim and says whether it holds. COHORT cannot do that without
contradicting itself. `VerificationMethod`'s docstring excludes
`MODEL_ENTAILMENT` in as many words — *"a second model's opinion is still
another agent's opinion, and admitting it as a formal verification method would
smuggle consensus-among-models back in through the side door"*. A reviewer
whose agreement promoted claims would be that side door, reopened one layer up:
agreement between two readers standing in for evidence, which is the same error
`independent_support()` catches between witnesses.

So the reviewer's evidence is mechanical — it re-fetches every cited passage
and re-locates the excerpt — and its judgment is asymmetric:

| reviewer says | spans re-verify | result |
|---|---|---|
| sound | yes | attested |
| sound | **no** | **not attested** |
| unsound | yes | not attested, objection recorded |

**A verdict can withhold promotion; it can never supply it.** A claim advances
on a re-verified span, never on something a model said, while a reviewer that
notices a citation does not support its claim can still stop it. Models are
good at re-checking locations and bad at adjudicating meaning, and only the
first is given force.

That is the difference from both siblings, and it is a real one rather than a
smaller version of theirs. Their reviewers can promote on judgment; ours cannot.
The cost is honest and worth stating: **a claim whose citations re-verify but
which reads more into them than they say will pass unless the reviewer
objects** — so `attested` still means "cited and located", never "true". The
human `accept` remains where truth is asserted, which is where this design has
always put it.

Still outstanding after this round: **formulaic-passage exclusion from
`independent_support()`** (the best idea taken from reading their code, item 1
above), a deterministic measurement layer models may only cite from (§8.4, now
recommended by two siblings independently), a measured scaling study, claim
versioning, and prior-art independence over secondary sources.
