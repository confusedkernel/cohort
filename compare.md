# Three systems from one brief

COHORT, Epistemic Swarm and graph-fact-check are three independent
implementations of the same essay. This is a comparison of what each one built
when the shared brief ran out.

Read off three working trees on **2026-09-02**, not estimated:

| | Repository | HEAD |
|---|---|---|
| **COHORT** | `~/cohort` (`confusedkernel/cohort`) — this repository | `6fd9f55` + the refusal-taxonomy work in progress |
| **Epistemic Swarm** | `~/epistemic-swarm` (`lopentu/epistemic-swarm`) | `3a37aa9` |
| **graph-fact-check** | `~/graph-fact-check` | `7c39d58` |

Every number below was read off a tree. Where a project's own document is
quoted, it is marked as a quotation and checked against its code.

> **This document rewrote itself once already.** Its first two editions were a
> two-way comparison with the third system bolted on as an appendix, first as
> hearsay and then as a verified column. Four of its recommendations to COHORT
> have since been implemented — model-family disjointness, edge retraction, an
> output-token cap, and a reviewer role — and one of its findings (a refusal
> census that could not name what it counted) came back from a live run and
> changed the code again. The rewrite is because the appendix shape was hiding
> the most interesting result: **the three projects are not three speeds of one
> thing. They guard three different kinds of independence, and each built the
> half the others left open.**

---

## 1. One sentence each

**COHORT** is a small, dependency-light evidence graph whose *write boundary*
makes one philological argument operational — that agreement between related
witnesses is not corroboration — and whose refusals are part of its output.

**Epistemic Swarm** is a self-hostable, queue-durable research instrument where
many models read the same pinned bytes under separated roles, everything is
recorded immutably, and the machine is never allowed to accept anything.

**graph-fact-check** is a stylometric attribution pipeline that answers a real
philological question — which canonical attributions are wrong — with a
deterministic evidence table, a second-family verifier, and a provenance
collapse over the scholarship that has answered it before.

---

## 2. They are siblings, and the evidence is specific

These are not three teams who happened to converge. COHORT and Epistemic Swarm
share an ancestor document with verbatim overlap; graph-fact-check names both
in its own comparison and traces all three to the *"Graph-Native Research"*
essay. The shared inheritance is concrete:

| Shared | COHORT | Epistemic Swarm | graph-fact-check |
|---|---|---|---|
| Corpus | CBETA v061 archive | same | **a different extraction** — see below |
| Archive SHA-256 pinned | ✅ `90a663f2…7158f2` | ✅ the same constant | ❌ no archive hash anywhere |
| Governing phrase *"evidential pluralism made auditable"* | ✅ verbatim | ✅ verbatim | ➖ same stance, different words |
| Refused anti-goal: consensus-seeking | ✅ | ✅ | ✅ |
| No ranking, merging or averaging of readings | ✅ | ✅ | ✅ escalates to a doubtful tier instead |
| Claims bound to source bytes | ✅ `verify_exact_span` | ✅ quote located in the TEI base, re-verified at review | ⚠️ cites ids from a measured evidence table; `verify_span()` is written and never called |
| Falsifiability required of a hypothesis | ✅ refused without a `tests` edge | ✅ refused without prediction/test/counterargument | ✅ auto-runs a held-out prospective test |
| Model transport | OpenRouter, stdlib `urllib` | OpenRouter behind an adapter | OpenRouter, stdlib `urllib` |
| Licence stance: corpus bytes never committed | ✅ | ✅ | ✅ |

COHORT and Epistemic Swarm do not reference each other anywhere, and neither
repository mentioned graph-fact-check until this document did.
graph-fact-check is the only one of the three whose own tree names the other
two. **Three independent implementations, one brief.**

### The corpus row is not the same row, and it matters

This is the sharpest factual correction to the previous edition of this
document, which recorded a shared corpus for all three.

COHORT and Epistemic Swarm both read
`CBETA_電子佛典_xml_v061_20210710.zip`, both hard-code the same SHA-256
(`90a663f2…7158f2`), and both carry the same warning in their documentation: do
**not** substitute the convenient already-extracted tree on the same server,
because a checked document differs from the archive copy.

graph-fact-check reads a different tree. `swarm/cbeta.py` documents its source
as *"the CBETA checkpoint (pulled from `rainbow:/mnt/md0/corpus/cbeta`)"*, and
`ROADMAP.md` records what was pulled: a **28-text working set** copied locally
out of 7,926 TEI-like XML files, in a `<w>`-tokenised variant whose running
text is reconstructed by joining tokens — a different markup shape from the
archive's TEI. Its canon-wide document frequency is not computed locally at all:
`corpus_search.py` **SSHes into `rainbow` and runs a shell script** against
`/mnt/md0/corpus/cbeta/cbeta_xml_original`.

Nothing in the tree pins a hash for any of it. `hashlib` appears once, hashing
a document's reconstructed text after the fact (`cbeta.py:67`), which
fingerprints what was read rather than establishing what should have been read.

Two consequences, neither of them theoretical:

1. **Its offsets and its siblings' offsets are not the same coordinates.** A
   span citation from one is not checkable against the other, so the three
   cannot audit each other's byte-level evidence even where they read the same
   text.
2. **This is the findings paper.** Its verdicts about canonical attributions
   rest on an unpinned copy of a corpus whose pinned form both siblings treat as
   a precondition — and on a remote shell for the canon-wide half. That is the
   exact substitution both siblings' documentation warns against, made by the
   one project whose output is claims about the texts rather than claims about
   the machinery.

---

## 3. The spine: three kinds of independence

Every one of these projects starts from *agreement is not truth*. The
interesting question is **whose agreement each one distrusts**, and they give
three different answers.

### Epistemic Swarm distrusts the readers

Its reviewers must come from a **model family disjoint from every lens model**,
enforced at the configuration boundary — a roster with overlapping families is
refused before a call is made. Its scaling study ran four families at once (GLM,
Gemma, DeepSeek, Mistral). The worry is shared training priors: two models
agreeing may be one model twice.

It goes further than model choice. Lens charters containing consensus language
— *"agree"*, *"converge"*, *"reconcile"* — are **refused at the configuration
boundary**. You cannot ask this system for a consensus even if you want one.

### COHORT distrusts the witnesses

`independent_support()` flips a claim's `independent` flag to `False` the moment
a `descends_from` or `parallel_of` edge links two of its attesting *witnesses*.
The worry is shared manuscript descent: two witnesses agreeing may be one
transmission event seen twice. `demo.py` exists to show it in three lines —
support stays at 2 while independence flips false.

COHORT has since adopted Epistemic Swarm's half as well, in response to the
first edition of this document. `cohort/families.py` defines family as the
OpenRouter provider prefix, and the rule is enforced **twice**, because neither
enforcement point subsumes the other:

- `cohort/agents/roster.py` refuses a roster whose agents overlap, when a run is
  assembled — but cannot see agents registered by a different run.
- `Graph.attest()` refuses the *write*, whoever assembled the writer — but
  cannot see a run that has not written yet.

The file says plainly what the heuristic cannot do: it catches a roster filled
from one provider and cannot catch the same weights served under two provider
names. *"A floor on independence, not a proof of one."*

### graph-fact-check distrusts the citations

Its `priorart.py` is COHORT's thesis applied one layer up, to the **secondary
literature**. `harvest()` keeps only URL-backed citations; `collapse()` counts
distinct named scholarly origins *and* distinct web hosts, and flags relay. Its
headline instance: **six scholars collapse to two evidentiary sources, verdict
`RELAYED`** — six citations that looked like six independent authorities are two
origins with four echoes, so a hypothesis that looked novel is correctly
self-labelled *rediscovered*.

It also does witness-level descent, and here it is ahead of COHORT in a way
worth naming. Its descent links are *detected* from shared passages, so it
needs an exclusion its siblings do not: `CbetaCorpus.is_boilerplate()` flags
colophons and stock openings, and `checks()` unions witnesses only across
non-boilerplate links. **100 of 146 shared-passage links in its run were
excluded on this ground** — the shared text among the witnesses it studied was
dominated by the attribution colophon itself, which is textbook circular
confirmation, caught mechanically.

### The three-way reading

| Whose agreement is suspect | Epistemic Swarm | COHORT | graph-fact-check |
|---|---|---|---|
| The **readers** (model priors) | ✅ disjoint families, explicit family lists, 4 run at once | ✅ provider-prefix floor, enforced at roster *and* write | ⚠️ 2 families by construction (GLM worker, Llama verifier); no rule |
| The **witnesses** (manuscript descent) | ❌ no stemmatic relation of any kind | ✅ `independent_support()`, the project's thesis | ✅ detected overlaps, with boilerplate excluded |
| The **citations** (literature provenance) | ⚠️ paper acquisition, but no collapse | ❌ prior-art search runs against the corpus only | ✅ `collapse()` over named origins *and* hosts |

No project has all three with teeth. Each has the one it was built for, and the
strongest version of any of them would have the other two.

**A note on where Epistemic Swarm's absence is felt.** Its own commissioned
external reviewer put it bluntly: *"No commentarial, translation-historical, or
stemmatic content appears, despite the charters."* It is close — its
`collation-worker.ts` deterministically extracts the TEI critical apparatus,
the Taishō base reading and each 宋/元/明 witness variant, and records an empty
collation as the honest finding *"no witness varies here."* COHORT's
`collate_editions` reads the same markup. The difference is what happens next:
Epistemic Swarm records witness variation **as evidence for a human to read**,
COHORT converts it into a graph relation **that mechanically discounts
support**. One surfaces the fact; the other makes the fact change the
arithmetic.

---

## 4. Two infrastructure papers and one findings paper

This is the difference that makes the three genuinely incomparable on a single
axis, and it should be said out loud before PNC, since all three may present.

COHORT and Epistemic Swarm both state in their own documents that the
contribution is 工具層 / methodological infrastructure and explicitly **not** an
argument about textual history. COHORT's design doc lists content-layer claims
among its anti-goals in as many words: *"Do not ship an argument about textual
history dressed as a demo."* Epistemic Swarm's status report closes with *"The
content-layer questions stay with the philologists, which is the point."*

graph-fact-check's deliverable is `out/attribution/report.md`, and it is a
philological argument: per-text verdicts, an eigen-word fingerprint table, and
an escalated doubtful tier. T1492, T2027, T0091 and T0092 are reported as
likely misattributed; T1470, T0109 and T0112 are escalated as doubtful rather
than averaged into a middle answer. It is doing, deliberately and with a
verifier, the thing COHORT rules out for itself.

That is not a criticism. It is the reason the three do not share a yardstick,
stated more precisely than *throughput versus discipline*:

**An infrastructure paper is judged on whether the machinery refuses the right
things. A findings paper is judged on whether the findings are right.**

Scale and accuracy numbers are the correct yardstick for graph-fact-check and a
category error for the other two. "Architecturally cleanest but no accuracy
numbers" is only a weakness if COHORT were trying to be the third kind of paper.

It cuts the other way too, and harder. The findings framing **raises** the
evidentiary stakes rather than lowering them — and graph-fact-check's own design
document knows it. `BUDDHIST_ATTRIBUTION_PIPELINE.md` §4 step 5 T3 calls a human
`accept` before an attribution result is citable *"non-negotiable"*: **"no
auto-published re-attribution of a canonical text."** Nothing in the tree
implements it. A grep for `accept` / `citable` / `human` across `swarm/` returns
one unrelated string inside a prompt, and `report.md` publishes machine-only
verdicts on canonical attributions. This is its own stated requirement, unbuilt,
in the one place where it matters most.

---

## 5. The promotion ladder: a clean three-way split

Nothing separates the three more cleanly than *what a machine is allowed to
conclude*.

| | Epistemic Swarm | COHORT | graph-fact-check |
|---|---|---|---|
| Machine may promote a claim | **Never.** Claims stay at `EVIDENCE_ATTACHED` | **Yes**, `proposed → attested`, on mechanically re-verified spans | **Yes**, straight to a published verdict |
| Human may promote a claim | **Not implemented.** Even a human review event carries a literal `acceptsClaim: false` | **Yes**, `accept` — the only path to citable, `NotResearcher` refuses anyone else | No gate exists |
| Can a claim ever become citable? | No. The downstream half of its own epistemic policy cannot yet run | Yes | Everything in `report.md` already is |
| Researcher can act from the interface | ❌ workbench is GET-only; the action registry is unreachable from it | ✅ accept, reject, reopen, attest, retract-edge, restore-edge — CLI and UI both | ➖ no interface |

Each position has a cost, and each project pays a different one.

**Epistemic Swarm** treats machine-proposed acceptance as dangerous enough to
leave unimplemented and makes *withholding* the safe default — so its claims can
never become citable, and the synthesis half of its own policy is unreachable.

**COHORT** treats the researcher's signature as the point of the whole ladder —
*"only accepted nodes may be cited or used as premises by other agents"* — so it
had to build the button, which means its safety rests on the ladder's
preconditions actually being right.

**graph-fact-check** publishes. Its verdicts are the product, and its own
requirement for a gate is the largest unbuilt item in its tree.

### COHORT's reviewer, and why it is not a second opinion

The reviewer role was the sharpest criticism the first edition of this document
received — graph-fact-check's own table said COHORT had *"mostly single-model
attestation workers; no cross-model reviewer."* True when written. It is now
built, and **how** it is built is the part worth recording, because the obvious
implementation would have contradicted §3.

Both siblings' reviewers are, in part, entailment judges: a second model reads
the claim and says whether it holds. COHORT cannot do that without contradicting
itself. `VerificationMethod`'s docstring excludes `MODEL_ENTAILMENT` in as many
words — *"a second model's opinion is still another agent's opinion, and
admitting it as a formal verification method would smuggle consensus-among-models
back in through the side door."* A reviewer whose agreement promoted claims
would be that side door reopened one layer up: agreement between two readers
standing in for evidence, which is exactly the error `independent_support()`
catches between witnesses.

So the reviewer's evidence is mechanical — it re-fetches every cited passage and
re-locates the excerpt — and its judgment is **asymmetric**:

| reviewer says | spans re-verify | result |
|---|---|---|
| sound | yes | attested |
| sound | **no** | **not attested** |
| unsound | yes | not attested, objection recorded |

**A verdict can withhold promotion; it can never supply it.** A claim advances on
a re-verified span, never on something a model said, while a reviewer that
notices a citation does not support its claim can still stop it. Models are good
at re-checking locations and bad at adjudicating meaning, and only the first is
given force.

This held live. In the third of three live three-model runs, a claim —
*"色即是空 is attested in both extant Chinese translations"* — had **all ten of
its cited passages re-fetch and match byte for byte** and stayed at `proposed`
anyway, because the reviewer returned `unsound`: the phrase is in Xuanzang's
T 251 and not in Kumārajīva's T 250. The verification records `result=pass` at
A2 for the spans, with the reviewer's reading in `limitations` and the machine's
in `detail`. A model verdict withheld a promotion it could never have supplied,
and the disagreement is in the record instead of being resolved into one answer.

The cost is honest and worth stating: **a claim whose citations re-verify but
which reads more into them than they say will pass unless the reviewer
objects** — so `attested` still means "cited and located", never "true". The
human `accept` remains where truth is asserted.

---

## 6. Implementation, side by side

| | COHORT | Epistemic Swarm | graph-fact-check |
|---|---|---|---|
| Language | Python 3.11+ | TypeScript / Node 22 | Python, **stdlib only** |
| Runtime dependencies | **1** (`pydantic`); `fastapi`+`uvicorn` behind an optional extra | `fastify`, `pg`, `pg-boss`, `yauzl`, `zod`, `pi-coding-agent` | **0** |
| Store | SQLite projection + append-only JSONL | PostgreSQL, append-only ledger, DB-level immutability triggers | `out/attribution/` JSON + Markdown, **overwritten per run** |
| Ground truth | **The JSONL log.** SQLite is rebuildable from it, and a test asserts the diff | **The ledger itself.** PostgreSQL recomputes SHA-256 from stored bytes | None — no event log, no replay |
| Source LOC | 8,028 package + 4,170 frontend | 19,993 `src/` | 2,525 across 10 modules (+812 lines of design docs) |
| Tests | **390**, 6,270 LOC | 56 modules — ~600 hermetic, 210 PostgreSQL, 11 browser, plus an archive-gated e2e suite | **none.** No test directory, no `pyproject.toml`, no runner, no assertion-bearing module |
| Migrations | 5 | 9 | ➖ |
| Concurrency | `asyncio` in one process, one shared `Graph`, one exclusive non-blocking `fcntl.flock` | `pg-boss` durable queue, multiple worker processes, leases and retries | `ThreadPoolExecutor(max_workers=16)` |
| Front end | React + Vite SPA — **read/write** | Server-rendered HTML + one vanilla JS file — **read-only** | Static `vis-network` HTML — read-only |
| CLI | `cohort`, **18 commands**, parity with the web UI **enforced by a test** | 13+ npm scripts, mostly operational stages | one entry point |
| Lint / format | none configured, by house rule | eslint, prettier, knip dead-code, ruff + ty | none |
| To run it at all | `pip install`, then a file | PostgreSQL 15+, `db:migrate`, a worker process, a dispatch pass, then the run | `python -m swarm...`, plus a venv for the ATELIER bridge |

Two things worth calling out in each direction.

**Epistemic Swarm is strongest on defence in depth.** Immutability is enforced by
database triggers, not only by application discipline; hashes are recomputed by
PostgreSQL from stored bytes rather than trusted as declared; CI runs typecheck,
format, dead-code and browser tests on every change. COHORT relies on one process
holding one lock and on tests to catch drift.

**COHORT is strongest on the log being primary.** Its ground truth is a text file
you can read with `cat`, and `rebuild()` proves the database is a faithful
projection of it — a property Epistemic Swarm does not need, because its ledger
*is* the database, but also cannot offer.

**graph-fact-check is strongest on getting out of its own way.** Zero
dependencies, ten modules, and it produced a philological result. The cost is
the whole right-hand column of the durability rows: nothing is replayable,
nothing is recoverable, and a re-run destroys the previous answer. Its own
comparison document lists persistence as something it *"lack[s] entirely"*,
which is the axis COHORT is built on.

---

## 7. Scale, measured

Each project's largest run, as recorded in its own tree:

| | COHORT | Epistemic Swarm | graph-fact-check |
|---|---|---|---|
| Largest run | 3 agents on **3 model families** (`z-ai`, `deepseek`, `qwen`) — 2 workers + 1 reviewer | **28 executions** (16 lenses / 8 reviewers / 4 proposers) | **93 calls**, 42-agent fan-out (24 scouts, 18 assessors) |
| Wall time | 62.8 s for the 2-agent run | 680 s | **not instrumented** |
| Tokens | 54,036 across the demo graph's 21 calls | 92,389 | 533,344 |
| Cost | **$0.00402** (12 calls) | **$0.0203** | **~$0.10–0.15 (estimated)** |
| Per call | ~$0.0003 | ~$0.0007 | ~$0.0011–0.0016 |
| Scaling evidence | ❌ no study | ✅ **four-point table** (4 / 8 / 15 / 28 execs), 0 infrastructure failures over 55 executions | ❌ one run |
| Integrity re-checked after the run | ✅ 95 events → 40 nodes / 45 edges, **0 mismatched payload hashes** | ✅ ledger hashes recomputed by the DB | ❌ nothing to re-check |

Three honest readings of that table.

**Epistemic Swarm has done the measurement work the other two have not.** Its
scaling study is the only place any of the three shows what happens as the swarm
grows, and its findings are non-obvious: interpretation plurality scales
*linearly* (13 distinct theses at 13 admitted lenses — nothing merged or dropped
a reading as the roster grew), cost scales linearly at ~$0.0007/execution, wall
time per execution *falls* from ~31 s to ~24 s under wave concurrency, and
**small swarms are fragile** — at 2/1/1 the single reviewer was boundary-rejected
and every claim lost its entailment judgment. Size buys redundancy. That is a
result, and neither sibling can currently produce one.

**COHORT's cost figure is not a virtue, it is a scale.** $0.004 is what three
agents cost. What is *not* demo-scale is the corpus: the real hash-verified CBETA
v061 archive with a full-corpus FTS5 index over **15.28M citable spans across all
20,190 entries**, every hit fetchable by construction. Real corpus, small run —
and graph-fact-check's *"still demo corpus"* is the one line in its comparison
that the tree does not support.

**graph-fact-check pays the most and measures the least.** Its 1.7× tokens per
call over Epistemic Swarm is partly a reasoning model with nothing bounding its
output, and its own document names both the missing output cap and the missing
wall-clock as its binding constraints. The wall-clock is a one-line fix:
`client.py:62` already returns `latency` per call and `_fold_usage` folds only
the three token counts.

---

## 8. Feature matrix

| Capability | COHORT | Epistemic Swarm | graph-fact-check |
|---|---|---|---|
| **Shared-descent discounting between witnesses** | ✅ `independent_support()` | ❌ | ✅ detected, boilerplate excluded |
| **Boilerplate excluded from descent** | ➖ n/a — nothing detects descent yet | ➖ n/a | ✅ **100 of 146 links excluded** |
| **Disjoint reviewer model families** | ✅ provider-prefix floor, roster + write boundary | ✅ **explicit family lists, config boundary** | ⚠️ 2 families by construction, no rule |
| **Prior-art collapse over the literature** | ❌ corpus-only prior art | ⚠️ acquisition, no collapse | ✅ **6 scholars → 2 sources = RELAYED** |
| Byte-exact source pinning | ✅ hash-verified archive, `source_ref` re-fetch | ✅ hash-pinned excerpts, re-verified on read | ❌ unpinned corpus checkpoint; `verify_span()` written, never called |
| Verbatim quote required per claim | ⚠️ excerpts carried; no verbatim gate at admission | ✅ deterministic location in the TEI base; fabricated quote rejected | ✅ different guarantee — must cite a measured evidence id; fabricated cites filtered |
| **Deterministic measurement before interpretation** | ❌ tools return spans; agents compute | ✅ census worker — *"models are never used as counters"* | ✅ `build_evidence()` — Delta, eigen coverage, register ratios, genre baselines |
| Full-corpus search index | ✅ FTS5, 15.28M spans, ~65 ms | ⚠️ researcher names spans | ✅ canon-wide grep verification over 7,926 docs |
| Critical-apparatus collation | ✅ `collate_editions`, joint sigla never split | ✅ `collation-worker`, empty collation is a finding | ❌ |
| Quantitative stylometry / authorship distance | ❌ | ❌ | ✅ **Burrows's Delta, eigen-word discovery (df ≤ 80), char-trigrams** |
| Impostor baselines per genre | ❌ | ❌ | ✅ a 0/38 in an uncovered genre is *not discriminating*, not evidence |
| Falsifiability gate on hypotheses | ✅ refused without a `tests` edge | ✅ refused without prediction/test/counterargument | ✅ + auto-runs the held-out test |
| Held-out prospective test as a pipeline stage | ❌ | ⚠️ run manually as a study | ✅ `hypothesize_and_test()` |
| Contradiction as first-class | ✅ `contradicts` edge, reason mandatory | ✅ `opposes` links on interpretations | ⚠️ doubtful tier, not an edge |
| Consensus language refused at config | ❌ | ✅ | ❌ |
| Cross-model review | ✅ **asymmetric — may veto, never promote** | ✅ entailment recorded as evidence, never proof | ✅ Llama verifier over a GLM worker |
| Claim versioning / supersession | ❌ | ✅ typed `SUPERSEDES` | ❌ |
| Retraction | ⚠️ **edges yes** (migration 4), nodes reject-and-reopen only | ✅ typed `RETRACTS` | ❌ |
| Researcher accept → citable | ✅ live, CLI and UI | ❌ deliberately unimplemented | ❌ **required by its own design, unbuilt** |
| Append-only ground truth | ✅ JSONL log | ✅ PostgreSQL ledger | ❌ overwritten per run |
| Rebuild-and-diff integrity proof | ✅ | ➖ n/a (ledger is the store) | ❌ |
| Every model call recorded, failures included | ✅ | ✅ with prompt hashes | ⚠️ token counts folded; no per-call record persisted |
| **Refusal census with a taxonomy** | ✅ **5 categories, streak detection, 3 rot-guards** | ⚠️ rejections recorded, not classified or counted | ❌ |
| Durable queue / retries | ❌ | ✅ `pg-boss` | ❌ |
| Measured scaling study | ❌ | ✅ four sizes, published | ❌ |
| Output-token cap | ✅ 2,800, liftable only deliberately | ✅ 2,800 | ❌ named as its own gap |
| Wall-clock + cost metering per run | ✅ `elapsed_s`, `latency_ms`, cost, read back from the log | ✅ | ❌ `latency` returned and dropped |
| Paper acquisition | ❌ | ✅ content-addressed store; *a cache hit is not evidence* | ⚠️ live web fetch, no store |
| Live ATELIER integration | ❌ deferred to stage 6, stated plainly | ➖ not a target | ✅ `atelier_bridge.py` shells into ATELIER's venv |
| Self-hosting commitment | ❌ OpenRouter only | ✅ explicit open-source boundary policy | ❌ |
| External adversarial review, archived | ❌ | ✅ **4 reviews, 2 rounds, verbatim** | ❌ |
| CLI/UI parity, enforced | ✅ by test | ❌ | ➖ |
| Access governance | ❌ deferred to ATELIER, stated plainly | ❌ not addressed | ❌ |

---

## 9. What only one of them has

The most useful column in the matrix is the one where two cells are empty.

**Only Epistemic Swarm has:** a measured scaling study; durable queue dispatch
with retries; database-enforced immutability; claim versioning with typed
lineage; a self-hosting policy that names OpenRouter as temporary; commissioned
external adversarial review, twice, archived verbatim; and consensus language
refused at the configuration boundary.

**Only COHORT has:** an event log as ground truth with a rebuild-and-diff proof
that the database is a faithful projection of it; a human `accept` that is both
implemented and reachable from two interfaces; enforced CLI/UI capability
parity; an asymmetric reviewer that can veto but not promote; and **the refusal
census**.

**Only graph-fact-check has:** quantitative stylometry — Burrows's Delta,
eigen-word discovery verified rare canon-wide, char-trigram similarity; per-genre
impostor baselines; provenance collapse over the secondary literature; a
corpus-*search* swarm that mines for candidate markers rather than interpreting a
given span; an auto-run held-out prospective test; and a live ATELIER bridge.

### The refusal census, which is new since the last edition

COHORT's most distinctive output was always the set of **refused writes**. What
was missing is the step that makes a list of them useful: forty refusals answer
no question a researcher has. The question is always *which of these should I
read?*

Every rule in `errors.py` now carries a category saying **what it indicts** —
`evidence` (go and look at the texts), `standing` (the discipline held),
`expression` (the writer could not say what it meant), `operational`, and
`unclassified`, which is reported and never dropped. Three guards keep it from
rotting: a test fails if a `CohortError` subclass has no category, fails again if
a category names a rule that no longer exists, and a third reads the tool layer's
own **AST** and fails if any tool raises something the census cannot name.

**Streaks are the finding.** A run of refusals from one agent, against one rule,
with nothing else of its own in between — consecutive within one *author's* own
sequence, so several agents interleaving does not destroy the signal precisely
when the most are running. One `expression` refusal is a model slip; a run of
them is the shape of a gap in the tool layer.

That third guard exists because the first two missed something, and this is the
part worth reporting to the siblings. The census was built and tested against a
demo log before it had ever seen a live run. On 2026-09-02 it saw three:

- **Run 1 — one refusal, `unclassified`.** `propose_claim` refused an ungrounded
  claim, the design's flagship evidence refusal, and it arrived under the rule
  name `ValueError`. Nine bare `ValueError` raises were spread across the tool
  layer, so a reviewer barred from a claim (`standing`), a mistyped id
  (`expression`) and a claim the corpus would not support (`evidence`) all landed
  in one bucket under one meaningless name. They are now `UngroundedClaim`,
  `WrongNodeType`, `SourceRefMissing` and `InvalidVerdict`.
- **Run 2 — 12 refusals, and a streak of five.** With the rules named, the
  picture resolved: 5 `UngroundedClaim` and 7 `NodeNotFound`, the largest streak
  being **all five of the reviewer's reviews, refused in a row**, each on an id
  with the `claim:` prefix stripped off. The second worker did it twice more, on
  ids `propose_claim` had just handed it. **Three models on three families making
  one mistake is not three coincidences** — and here the signal appeared *across*
  families rather than within one agent, which is stronger than a streak. The
  cause was ours: a listing that rendered `claim:` as a field label. The id is now
  quoted and the prefix named as part of it, and the refusal teaches — a
  prefix-less id matching exactly one node comes back *"did you mean
  `claim:abc…`? An id carries its type prefix, which is part of the id and not a
  label on it."* The malformed id is still refused; silently repairing it would
  teach that the type is decoration.
- **Run 3 — zero refusals.** Both claims reviewed, one promoted, one withheld on
  the reviewer's reading. 95 events replayed to 40 nodes and 45 edges, 0
  mismatched payload hashes. A zero is a fact: it says the two fixes landed.

**It counts; it does not conclude.** Nothing decides that a tool is missing —
that is a judgement, and the point of counting is to put it in front of someone
who can make it.

This is offered to both siblings as a mechanism rather than a boast. Epistemic
Swarm records boundary rejections richly and does not classify or count them;
its scaling table has a `Claims with failed review coverage` row that goes
6 → 6 → 0 → 5, which is exactly the shape a census would explain. graph-fact-check
records nothing that survives a re-run.

---

## 10. Convergent evolution — where two or three arrived independently

When independent implementations of one brief converge on a mechanism nobody
specified, that is the strongest evidence in this document.

**All three: measure first, let models interpret.** Epistemic Swarm built a
**census worker** after its external reviewers demanded one, and now hands
reviewers the counts as given — because a reviewer model had contradicted a
correct claim by recounting a juan by hand and getting 24 where the census gives
25. The false FAIL sits in the ledger next to the computation that refutes it,
and the miscount has not recurred. graph-fact-check arrived at the same place
from the other direction: `build_evidence()` computes Delta, eigen coverage,
register ratios and genre baselines mechanically, and a worker's claim is
*dropped* unless it cites one of those ids, with fabricated cites filtered
(`attribution.py:387`).

**Two of three now do it. COHORT does not.** Its tools return spans and compute
nothing, so its agents compute everything themselves and can therefore miscount.
This is the single strongest recommendation in this document precisely because
two siblings reached it separately, for different reasons, and one of them has a
recorded incident showing what it prevents.

**All three: the falsifiability gate.** Refusing a hypothesis that carries no
prospective test appears in all three, in three different shapes. Nothing in the
shared brief required it as a *boundary* rather than a prompt.

**Two of three: append-only ground truth with recomputed hashes.** COHORT's
JSONL log with `verify_integrity()`, Epistemic Swarm's ledger with PostgreSQL
recomputing SHA-256 from stored bytes. graph-fact-check has neither, and says so.

**Two of three: an output-token cap of exactly 2,800.** Epistemic Swarm set it;
COHORT adopted it from graph-fact-check's cost note, which was addressed to its
*own* pipeline and applied here. graph-fact-check still has none, and names it as
the reason it pays 1.7× per call.

**All three refuse to rank, merge or average.** Two record incompatible readings
side by side permanently; the third escalates to a doubtful tier rather than
splitting the difference. Not one of them has an averaging function anywhere.

---

## 11. What each should take from the others

### COHORT should take

1. **A deterministic measurement layer** models may only cite from — the census
   worker / evidence table. *Recommended by two siblings independently, which is
   why it is first.* It would let COHORT's agents reason over a whole juan
   without trusting a model to count.
2. **A measured scaling study.** One table at four sizes would replace an
   assertion with arithmetic — the house rule, applied to itself. Scaling
   currently rests on one two-agent run while a sibling publishes four points.
3. **Prior-art independence over secondary sources.** `propose_conjecture`
   requires a prior-art query and runs it **against the corpus only**, so COHORT
   cannot tell you whether a conjecture is already known to the literature. This
   is COHORT's own thesis, unapplied one layer up, and a sibling has it working.
4. **Claim versioning with typed lineage.** Edge retraction is built; corrections
   to *claims* are still coarse — reject-and-reopen, not a new version.
5. **A self-hosting position.** OpenRouter is still the only model path.
6. **Sequencing rule, if shared-passage detection is ever built:** the boilerplate
   exclusion belongs in the **same change** as the detector, not the one after.
   COHORT does not have graph-fact-check's problem today — `link_parallels` writes
   only CBETA's *asserted* `<cb:docNumber>` cross-references, a curator's
   statement rather than an inference from shared text, and nothing writes
   `descends_from` at all. It acquires the problem the moment descent is detected
   rather than attested.

### Epistemic Swarm should take

1. **A shared-descent relation with teeth.** It already extracts witness variation
   deterministically. One `descends_from` / `parallel_of` relation plus an
   independence computation would turn that evidence into a *correction*, and
   would answer its own reviewer's "no stemmatic content" objection at the level
   of mechanism rather than prompt. Both siblings have it; it is the only one of
   the three kinds of independence it does not guard.
2. **A researcher who can act from the interface.** The workbench is GET-only and
   the action registry is unreachable from it, so the downstream half of its own
   epistemic policy cannot run.
3. **A refusal census.** It records boundary rejections richly and never counts or
   classifies them. Its own scaling table shows failed review coverage moving
   6 → 6 → 0 → 5 across sizes with no mechanism to say why.
4. **Enforced CLI/UI capability parity.** Six sequenced shell commands with long
   environment-variable payloads is a real barrier for the PNC audience.

### graph-fact-check should take

1. **Pin the corpus.** Both siblings hash-verify
   `CBETA_電子佛典_xml_v061_20210710.zip` before reading a byte of it, and both
   warn in as many words against the convenient extracted tree. graph-fact-check
   reads a 28-text checkpoint pulled from a different path, in a different markup
   shape, with no archive hash, and reaches the rest of the canon over SSH. For
   the one project of the three whose output is verdicts about the texts, this is
   the load-bearing one: **an unpinned corpus makes every span citation
   unreproducible by anyone else**, including by its own next run.
2. **The human accept gate its own design calls non-negotiable.** *"No
   auto-published re-attribution of a canonical text"* is its rule, and
   `report.md` is machine-only. Both siblings treat machine acceptance as the
   thing not to build: Epistemic Swarm refuses it outright, COHORT routes it
   through a `NotResearcher` refusal that is a few lines long.
3. **Persistence.** An append-only run log costs one file and buys replay, a
   record of what was refused or dropped, and a run that does not destroy the
   previous answer. It lists this itself as something it lacks entirely.
4. **Tests.** No test directory, no `pyproject.toml`, no runner, no
   assertion-bearing module anywhere in the tree. Epistemic Swarm gates on ~800
   cases across four suites, COHORT on 390. **The three-way spread on this axis is
   wider than on any other**, and it matters most for the findings paper, whose
   output is verdicts about canonical attributions rather than an instrument.
5. **Wire `verify_span()`.** It is defined at `cbeta.py:141` and never called. Its
   own design section T1 says *"a claim whose span doesn't verify is rejected
   before any model sees it."* Grounding is enforced differently and genuinely —
   workers may only cite ids from the measured evidence table — but the guarantee
   is *"cites a measured evidence item"*, not *"quote re-verified against the
   bytes"*, which is what both siblings check.
6. **An output-token cap and the wall-clock fold.** Both are named in its own
   comparison as binding constraints. `client.py:62` already returns `latency`;
   `_fold_usage` drops it. One line.

---

## 12. Are they working toward the same direction?

**At the level of the thesis: yes, almost exactly.** All three refuse consensus,
none ranks or averages, all three tie claims to source bytes in some form, all
three put a falsifiability gate in front of novelty, and all three insist a human
decides — though only one has built the place where that happens. If any of the
three ideology sections were dropped into either other repository, very little
would need changing.

**At the level of the instrument: no, and productively so.** They have
specialised in three directions from one starting point, and each one's risk is
the shadow of its strength:

- **COHORT is an argument with a demo attached.** Small, portable, built around
  one claim — that corroboration weighting is invalid for transmitted corpora —
  with a mechanism that makes the claim operational and a three-line demo that
  shows it. *Its risk:* the machinery around the argument is thinner than the
  argument deserves. Scale and measurement are still assertions.
- **Epistemic Swarm is an instrument with an argument attached.** A
  production-shaped research platform with durable queues, immutability triggers,
  a four-point scaling study and four archived external reviews. *Its risk* is the
  one its own reviewer named: the epistemics are impeccable and the philology is
  undergraduate, because nothing in it models transmission.
- **graph-fact-check is a finding with an instrument attached.** The only one of
  the three that answered a philological question, with stylometry neither
  sibling has and a provenance collapse over the literature that is genuinely
  novel. *Its risk:* it publishes verdicts on canonical attributions from a tree
  with no tests, no persistence, no human gate, and an unpinned corpus — four
  things its siblings spent most of their code on, one of which its own design
  document declares non-negotiable, and one of which both siblings' documentation
  explicitly warns against.

The honest summary is a triangle, not a ranking:

> **graph-fact-check has the sharpest result. COHORT has the sharpest idea.
> Epistemic Swarm has the best instrument.** All three statements are true at
> once, and each project's largest gap is the thing another one of them already
> built.

---

## 13. Housekeeping — corrections to the record

Small factual items, kept because a document about independence should be
checkable.

- **The shared-corpus row was wrong in every previous edition of this document,
  including in the two-way sections that predate the third system.** All three
  read CBETA; only two read *the same pinned bytes*. §2 records what
  graph-fact-check actually reads and why the difference is load-bearing rather
  than pedantic. This document asserted a shared corpus for three editions on
  the strength of all three saying "CBETA", which is the same shape of error
  §3 exists to catch: a shared label mistaken for a shared observation.
- **`confusedkernel/meep` and `confusedkernel/cohort` are the same repository** —
  identical history. Not a separate offshoot. graph-fact-check's comparison
  establishes this correctly.
- **COHORT has no Anthropic dependency.** `BUDDHIST_ATTRIBUTION_PIPELINE.md` §1
  (dated 2026-08-31, marked design-only) lists COHORT as "Anthropic SDK",
  "Stage-1 core done; single worker; LLM mocked". It talks to OpenRouter over
  stdlib `urllib`, for the same reason `client.py` does.
  `SIBLING_SYSTEMS_COMPARISON.md` already supersedes that row; noted only so a
  reader of the older file does not take it as current.
- **"Still demo corpus"** is not right. The corpus is the real hash-verified
  CBETA v061 archive with FTS over 15.28M citable spans across all 20,190
  entries. What is demo-scale is the **run**.
- **"Mostly single-model attestation workers; no cross-model reviewer"** was
  entirely true when written, and was the most useful sentence anyone wrote about
  this project. Both halves are now answered — §3 and §5.
- **graph-fact-check's internal discrepancy:** the large run is 533,344 tokens in
  its comparison table and 549k in its `ROADMAP.md`; cost is `~$0.10–0.15 (est.)`
  in both. The estimate is a consequence of implementation rather than of care —
  OpenRouter returns `usage.cost` on every response and `_fold_usage` folds only
  the three token counts, so there is no exact figure to report.
- **This document's earlier caveat about hearsay is resolved and kept.** The third
  system's column was once attested-by-its-author rather than verified. The
  repository was then read, and **its author's self-report survived the check** —
  everything in their table that could be verified against the tree, was. That is
  worth more than the caveat was.
