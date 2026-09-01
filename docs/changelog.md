# Changelog

The development record, oldest first. Each entry is kept as it was written,
because this project's house rule is that a superseded conclusion should say so
rather than go quiet — several entries below were later reversed, and the
reversal is more informative than a tidied-up history would be.

**These are dated notes, not current state.** Test counts, "not yet run" and
"still open" inside an entry are true as of that entry and nowhere else. For
what is true now, read [handoff.md](handoff.md).

This log lived at the top of the old root-level `HANDOFF.md` until 2026-09-02,
which pushed that file's "Read first" section down to line 840. Splitting it out is the only change:
the entries are verbatim, reordered only to put the one misfiled entry
(*The researcher UI, first cut*) back in sequence.

---


## The archive blocker is resolved

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
(roadmap.md §14, and step 3 of the then-current handoff): **29/30 carry real `<app>`/`<lem>`/`<rdg>`
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

---


## The researcher UI, first cut (read-only) — and the first corpus-backed demo

**Update: the researcher UI (stage 5) is built and serving — read-only.**

> *Historical entry, partly superseded.* This was the first stage-5 update.
> Two of its conclusions were later reversed, by
> [*Three gaps … closed*](#three-gaps-between-the-code-and-the-paper-claim-closed)
> and [*The web UI reaches parity*](#the-web-ui-reaches-parity-with-the-python-api)
> below: accept/reject **is** built (and the lock-holding concern stated here
> was wrong), and the UI is no longer read-only — it also browses the corpus
> and launches agent runs. What still holds is everything about how the
> frontend honours design §10, `Graph.open_read_only()`, and the `CbetaReader`
> collection bug. Its counts and "not yet run" notes are as of that day.

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

**Accept/reject was deliberately absent, and was the open decision.**
design.md §13 puts it in stage 5, but those are researcher *writes*, and the
worry at the time was that a writing UI would hold the exclusive lock for as
long as a browser tab is open, stopping every agent run in the meantime. That
was wrong — a write takes the lock for one request, not one session — and once
that was seen, the endpoints were built. See *Three gaps … closed* below.

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

**What was still open as of this entry** (roadmap.md §14): the chronology
scheme — which remains open, and remains the researcher's call. The same
paragraph noted `propose_conjecture` had not yet run against real text; it has
since, see *`propose_conjecture` runs live against the real corpus* below.

---


## Stage 4's extraction layer: `parallel_of` and cross-edition collation

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

---


## The full-corpus search index

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

---


## `propose_conjecture` runs live against the real corpus

**Update: `propose_conjecture` has now run live against the real corpus** —
the last stage-2/3 capability that had never touched real text.
`scripts/run_conjecture_demo.py`, one agent, four turns, **$0.0039 total**
(`z-ai/glm-5.3-flash`). Spend is capped *in code*: the script wraps the
transport (`AttestationWorker` already accepts one, so no core changes) and
refuses the next request once OpenRouter's reported costs reach the cap — a
hard stop before a call, since a budget only checked afterwards is not a
budget. A response with no reported cost is charged an estimate rather than
zero.

The run produced one conjecture with a complete dossier, a real prior-art
search over the full corpus (20 hits), a `searched_for` edge, and a `tests`
edge — so it is attestable by the falsifiability gate. The content is
genuinely scholarship-shaped: that the four-clause unit
「色不異空，空不異色，色即是空，空即是色」 was transmitted as a fixed unit
already stabilised in Chinese before the extant recensions diverged, with
named alternatives (independent translation using conventional renderings,
descent from Kumārajīva's 大品般若 wording, scribal harmonisation).

**The interesting result is the failures.** Before succeeding, the agent made
**five `find_attestations` calls against node ids it invented**
(`prior_art_色即是空`, `new-claim-色即是空`, …). Every one was refused with
`NodeNotFound`, reported back to the model as a tool error, and the agent
adapted and completed the task. That is the write boundary working exactly as
designed — design.md §5 principle 4, refusals surfaced rather than silently
dropped — and it is the first time that path has been exercised by a real
model rather than a test.

The root cause was a genuine gap: **an agent had no tool for creating a
`claim`**, so when it wanted attestations for something not yet in the graph
it fabricated an id instead. **This has since been fixed — see the
`propose_claim` section below.**

One incidental validation: the model's own `selection_risks` warned that "the
FTS may normalize punctuation and variant characters, merging distinct
recensions". That is a real property of FTS5's unicode61 tokenizer — and it is
already mitigated, because `cbeta_fts.search()` re-checks every candidate for
an exact substring match in Python, so returned hits are exact. The risk was
correctly identified and is already handled.

---


## `propose_claim` — the tool the conjecture run showed was missing

**Update: `propose_claim` is built — the tool the conjecture run showed was
missing.** An agent can now create a `claim`, so the loop that previously
dead-ended in five fabricated ids closes: propose the claim, then call
`find_attestations` on the id the first call returned.

It is deliberately **not** a bare one-field write. `ClaimPayload` asks only
for `text`, so an unguarded tool would be markedly *cheaper* than
`propose_conjecture` (four-field dossier, prior-art search, prospective
query). That asymmetry would be a bypass: anything an agent could not get
past the falsifiability gate it could relabel as a claim, bolt on whatever
passages a search returned, and ride the ladder to `attested` with no
dossier — precisely the "vacuous grounded claim" design.md §7 says citation
checking "passes happily, because a claim can be perfectly cited and say
nothing".

The guard mirrors `propose_conjecture`'s prior-art step: the grounding query
is run against the corpus *before* the claim node is written, and a query
with no hits refuses the claim. Nothing is written on the refusal path — no
orphan claim, no orphan query node (tested). It is a **tool-level** check,
not a new write-boundary rule: `errors.py` owns state validity raised by
`graph.py` and nowhere else, so this raises a plain `ValueError`, the same
way `find_attestations` does for a wrong node type, and the worker reports it
back to the model like any other refusal.

The guard costs nothing legitimate. A claim whose grounding query returns
nothing has no passages to cite, so `attest()` would refuse it anyway
(`UnattestableClaim`) — the refusal just arrives one rung earlier. The one
case it genuinely turns away is the **negative claim** ("X does not occur in
this corpus"), and that case belongs in `propose_conjecture` on its merits:
an absence is settled by a retrieval, not by citation, which is exactly what
a `tests` edge records. The refusal message says so rather than leaving the
agent to guess.

The tool does not attach attestations itself — `find_attestations` already
takes a claim id and records `attests` edges through the same boundary, and
duplicating that here would give two tools two subtly different ways to
write evidence.

**One vocabulary change, deliberately minimal**: `searched_for`'s domain
widened from `{(query, conjecture)}` to also allow `(query, claim)`. A
claim's grounding search is the same kind of fact about the same kind of
node — a retrieval actually run before something was proposed — so it
belongs on that edge rather than on a second near-identical type. The
vocabulary stays closed; only this type's domain grew. `tests` is
deliberately **not** widened alongside it: a `tests` edge is what makes a
conjecture attestable, and letting one point at a claim would open a second
route past the falsifiability gate. A regression test asserts
`searched_for` still refuses a `query -> passage` edge.

`PROMPT_VERSION` is bumped to `attestation_worker/v3-propose-claim` so
logged `model_call` events stay groupable by the tool contract that produced
them. The system prompt now also says, flatly, never to invent a node id.

The UI needed no change: `query` already has a column and `searched_for`
already has an edge style.

Files: `cohort/tools/propose_claim.py` (new), `cohort/graph.py`
(`EDGE_DOMAINS`), `cohort/agents/attestation_worker.py`,
`tests/test_tools.py`, `tests/test_attestation_worker.py`. **Not yet run
against a live model** — the loop is proven by a fake transport that reads
the claim id back out of the tool-result message the way a model has to,
but no real API call has exercised it.

---


## Three gaps between the code and the paper claim, closed

**Update: the three gaps between the code and design.md §15's paper claim are
closed.** The §15 claim was tested clause by clause; two clauses were not
actually delivered and one vocabulary entry had no producer.

**1. The researcher now has an interface.** `accept`/`reject`/`reopen` existed
only as Python calls, so *researcher authority as mechanism* — the one thing
agents may never do (design.md §8) — could only be demonstrated by typing
Python. `POST /api/accept|reject|reopen` now exist behind
`create_app(..., allow_writes=True)` / `serve_ui.py --allow-writes`, off by
default.

An earlier version of `cohort/ui/api.py`'s docstring argued a writing UI
"would have to hold the exclusive lock for as long as a browser tab is open".
**That was wrong, and it was the only thing blocking this.** Each write calls
`Graph.open()` for one request and closes it, so the lock is held for
milliseconds. Single-writer discipline is unchanged, not relaxed: when an
agent run holds the lock, `flock` refuses and the endpoint answers **409**
with "Nothing was changed", rather than queueing, retrying, or weakening the
lock. Verified live against a real held lock, not only in tests. A refused
write answers **422** with the rule named (`MissingRejectionReason`,
`RungSkipped`), because a refusal is an answer from this system, not a server
fault — the UI shows the rule name, since the rule is the informative part.

Writes default to off because these endpoints act as `RESEARCHER`. Enabling
them is the operator asserting that whoever can reach the port *is* the
researcher, which is a claim only the operator can make.

**2. Refusals are readable — and some were never being recorded at all.**
This started as "add an endpoint" and turned up a real defect. `_refuse()`
only fires for rules the write boundary enforces on a write it was asked to
perform. `NodeNotFound` is raised by *lookup*, so the five refused
`find_attestations` calls in the live conjecture run were reported to the
model, adapted around — and **never written to the log**. `conjecture_run.jsonl`
records a clean run. §15's "refusals are part of its scholarly output" held
only for the subset of refusals that happened to be write-boundary rules,
which excluded the most common one a real agent hits.

Fixed with `Graph.log_refusal()`, called from `AttestationWorker._dispatch`,
which is the choke point that already knows a tool call failed and who
authored it. It is idempotent with `_refuse()` (via a `logged_to_event_log`
marker on the exception), so one refusal is still one event — there is a test
for exactly that. Both classes now land in the log with the `model_call_id`
that caused them, so cost and refusal join up.

`cohort.eventlog.read_refusals()` reads them (a pure log scan, same pattern as
`summarize_model_calls`; a refusal changed no state, so there is no row for it
in SQLite), `GET /api/refusals` serves them, and a panel in the UI shows them
with a per-rule tally and a plain-language note per rule. A missing log
reports `available: false` rather than implying zero refusals.

**3. `contradicts` has a producer.** It had been in the vocabulary since
stage 1, materialised in both directions, and drawn as heavily as `attests` by
the UI — while **nothing in the system ever created one**, so "disagreement
made visible" (§6) had no data behind it. `cohort/tools/record_contradiction.py`
writes them, requires a stated reason, refuses invented node ids and refuses
audit/query nodes (a `decision` is not evidence). It is registered in
`AttestationWorker`, so an agent can record disagreement — the COHORT-native
equivalent of a "challenge".

**Consequence worth knowing: edges have no ladder and no retraction.** A
node can be rejected; an edge cannot be removed. A wrong `contradicts` edge is
permanent, visible, and only annotatable. That is a real cost of registering
this tool for agents, and it is the reason the reason-string is mandatory
rather than optional.

**One schema change**: migration 3, `ALTER TABLE edges ADD COLUMN reason TEXT`.
`contradicts` is the only edge type whose domain is `"any"`, so the write
boundary can check almost nothing about it while the UI renders it as
prominently as evidence; "disagreement made visible" has to mean the *grounds*
are visible too. No backfill — edges written before this carried no reason and
inventing one would be fabrication. Projections at v2 are refused by
`open_read_only` until opened once for writing; `demo_graph.sqlite` was
re-seeded and `conjecture_run.sqlite` migrated.

`seed_demo_graph.py` now also seeds a real contradiction (a claim that the
wording was fixed in Chinese before the recensions diverged, against the
conjecture that they descend from a shared Sanskrit recension — incompatible
predictions about whether an extant Sanskrit witness matches all three) and
deliberately triggers one refusal, so the UI's contradiction rendering and
refusals panel both have data behind them.

Files: `cohort/tools/record_contradiction.py` (new),
`cohort/ui/frontend/src/RefusalsPanel.jsx` (new), `cohort/eventlog.py`,
`cohort/schemas.py` (`Refusal`, `Edge.reason`), `cohort/graph.py`
(`log_refusal`, `add_edge(reason=)`), `cohort/migrations.py`,
`cohort/ui/api.py`, `cohort/agents/attestation_worker.py`,
`scripts/serve_ui.py`, `scripts/seed_demo_graph.py`, and the frontend's
`api.js` / `App.jsx` / `DetailPanel.jsx` / `styles.css`.
`PROMPT_VERSION` is now `attestation_worker/v4-contradiction`.

**Not yet run against a live model**: `record_contradiction` has never been
called by a real model, same status `propose_claim` is in.

---


## The web UI reaches parity with the Python API

**Update: the web UI now reaches parity with the Python API.** Corpus
browse/search and an agent-run launcher are built, so what you can do in a
script you can do in a browser. Three opt-in flags, separate because they carry
different consequences — reading the corpus is free, accepting a finding is a
scholarly act, starting a run spends money:

```
scripts/serve_ui.py --db demo_graph.sqlite --corpus --allow-writes --allow-runs --max-budget 0.50
```

**Verified with a real live run started over HTTP**, not only with fakes:
$0.00236, 4 model calls, 129s, `propose_claim` → `find_attestations` → a claim
with 10 attesting passages across 7 witnesses. Rebuild-from-log still matches
(81 events, 37 nodes, 43 edges) and integrity is clean afterwards.

**That run had zero invented-node-id refusals.** The earlier conjecture run had
five, because an agent had no way to create a claim. This is direct evidence
that `propose_claim` fixed the underlying gap rather than just papering over it.

**Corpus endpoints** (`/api/corpus/search`, `/api/corpus/fetch`) call
`source.search()`/`fetch()` — a test asserts the endpoint returns exactly what
Python returns, so parity is checked rather than asserted. Search over the full
20,190-entry index answers in ~65ms. Three things travel with every response
because omitting them would misrepresent the corpus: the ordering is labelled
`"corpus order; no relevance ranking"` (a list that looks ranked but is not
would misstate which witnesses matter), truncation is flagged with the real
length alongside it, and `source_terms` carries the CC BY-NC-SA-equivalent
license into every response.

`?strip_markup=true` gives a readable view (114,461 raw chars → 32,339
readable), because a researcher should not have to read
`<cb:mulu type="其他" level="1">` to see the text. It is **display only** and
the response says so in two fields (`markup_stripped`,
`offsets_align_with_witness`): stripped text no longer shares offsets with the
witness, so an `EXACT_SPAN` verification built against it would record
positions pointing nowhere. Raw stays the default for that reason.

**The run launcher** (`cohort/ui/runs.py`) keeps the scripts' guarantees rather
than inventing web-only ones:

- **One run at a time**, enforced by the existing `flock`. A run holds the
  writer lock for its whole duration, so accept/reject answers 409 while one is
  going — that is design.md §5 principle 7 behaving normally, and the UI's job
  is to say so, not to work around it. Tested.
- **Spend capped in code, with a ceiling the browser cannot raise.** The
  client proposes a budget; `max_budget_usd` bounds it. A client-supplied
  number nothing checks is a suggestion, not a cap. Tested with `budget_usd:
  999`.
- **Background thread, polled status.** A model loop takes minutes; the request
  returns a run id immediately.
- **The API key never reaches the browser.**
- **No queue and no retry**, deliberately: a queue would let spend accumulate
  unseen, and a retry would make single-writer discipline feel like flakiness.

`BudgetedTransport` moved out of `scripts/run_conjecture_demo.py` into
`cohort/agents/budget.py`, so the script and the UI share one cap
implementation instead of two. It is now thread-safe (the UI reads spend from a
request thread while a worker thread accumulates it).

**Two real bugs found and fixed while building this:**

1. **My own first design was wrong.** `RunManager` initially called
   `worker.run_async(max_turns=1)` in a loop to get per-turn progress. That
   silently restarts the conversation on every call, discarding all prior tool
   results and paying the model to rediscover them. Fixed properly by adding
   optional `on_tool_call` / `should_stop` callbacks to `run_async`, so the
   worker keeps one continuous loop and reports outward. Progress reporting
   must not change what the agent knows.

2. **The corpus readers were not thread-safe, which would have broken the
   corpus endpoints in production.** `CbetaFtsIndex` and `LocalReader` hold a
   sqlite connection bound to its creating thread, and FastAPI serves sync
   endpoints from a threadpool. Both now use `check_same_thread=False` plus a
   lock around every query. The connections are `mode=ro`, so the lock is not
   about write safety — it is because one sqlite3 connection multiplexes a
   single cursor-bearing protocol and two concurrent `execute`/`fetchall`
   pairs can return each other's rows.

Files: `cohort/agents/budget.py`, `cohort/ui/runs.py`,
`cohort/ui/frontend/src/CorpusPanel.jsx`, `RunPanel.jsx` (all new);
`cohort/agents/attestation_worker.py`, `cohort/ui/api.py`,
`cohort/sources/cbeta_fts.py`, `cohort/sources/local_reader.py`,
`cohort/sources/cbeta_markup.py`, `scripts/serve_ui.py`,
`scripts/run_conjecture_demo.py`, and the frontend's `api.js` / `App.jsx` /
`styles.css`. New tests in `tests/test_ui_runs.py`.

**Still Python-only, deliberately**: building the FTS index, and
`.env`/API-key management. Both are one-time setup, and a web form is the wrong
place for a credential.

---


## UI restyled, plus real responsiveness

**Update: UI restyled (Apple-style dark), plus real responsiveness.**
`styles.css` was rewritten around Apple's dark system colours, which happen to
map cleanly onto the semantics already in use — systemBlue for support,
systemOrange for the discounting relations (a warning, not an error),
systemRed for contradiction, systemPurple for the falsifiability edge.

**design.md §10's three requirements were preserved, not restyled away**: status
is still its own visual channel, discounting edges still differ from supporting
ones in colour *and* dash pattern *and* weight (so none relies on hue alone),
and `contradicts` is still as heavy as `attests`. The polish is applied around
them.

The three tabs are a macOS-style segmented control: one recessed track with the
active segment raised out of it. (Traffic-light buttons were considered and
rejected — the researcher asked for tabs.)

**The detail panel floats** rather than docking: an inspector card overlaying
the graph, anchored to `.body` so it stays below the top bar, with blur, a
lifted shadow, a close button and Escape to dismiss. The point is not only the
look — docking reserved 410px that sat empty whenever nothing was selected, so
the graph now uses the full width. Three consequences handled deliberately:

- **Nothing selected** renders a small, quiet hint card instead of a
  full-height empty column, and it is `pointer-events: none` so it can never
  swallow a click meant for the graph beneath it.
- **It only renders on the Graph tab.** It is the graph's detail view, so
  overlaying the corpus browser or run launcher with it would cover unrelated
  content.
- **Narrow screens** turn it into a bottom sheet (≤820px), not a stacked
  column and never a removal — it is where a claim's support independence is
  shown, so a breakpoint that dropped it would drop the argument.

Other changes: translucent blurred top bar, filled accent on the default
action, press-scale feedback, `:focus-visible` rings (keyboard only), styled
scrollbars, tabular numerals wherever figures change, a pulsing badge while a
run is live, and slide-in on new tool calls. All motion is behind
`prefers-reduced-motion` — it is decoration, and the information is in the
colour and the text.

**Responsiveness, both senses:**
- Layout: three breakpoints (1180 / 900 / 620px). The detail panel becomes a
  stacked section rather than disappearing — it is where a claim's support
  independence is shown, so a breakpoint that dropped it would drop the
  argument.
- Interaction: corpus search now runs **as you type**, debounced 220ms. Search
  answers in ~65ms, so waiting for a submit added latency the index does not
  have. Every response is tagged with the query that asked for it and stale
  ones are dropped — debouncing alone does not stop an earlier request landing
  last and showing results for a phrase already moved on from.

**Two pre-existing gaps closed while in there**: `.badge.assurance` and
`.badge.t-*` were always rendered and never styled, so both fell back to a
neutral badge. Node type now carries a quiet tint (never as saturated as a
status colour — type is not a judgement), and assurance is monospaced and
neutral *except* `A0_UNCHECKED`, which is tinted because "nothing has been
verified" is the one value a reader should not skim past. Assurance
deliberately does not reuse the status palette: the two are orthogonal.

Nothing was dropped in the rewrite — verified by diffing defined selectors
against the old sheet, and by checking every class the JSX uses still resolves.

---


## Settings popover and a real light theme

**Update: settings popover + a real light theme.** A gear in the top bar opens
a floating settings panel (outside-click and Escape to dismiss, capture-phase
so Escape closes the popover without also deselecting the graph node). "Show
audit nodes" moved out of the top bar into it, and gained the one-line
explanation of what those nodes are — a reader who thinks the graph is complete
would overestimate how checked it is.

**Theme has three states, not a two-way switch**: `system` stamps no attribute
and lets `prefers-color-scheme` decide (and keeps following it); `light`/`dark`
stamp `data-theme` on `<html>` and win over the OS. The choice persists in
`localStorage`, every access wrapped in try/catch — a private window throws on
storage, and a theme toggle must never be what white-screens the app — and it
is applied in `main.jsx` **before** the first paint, since applying it in an
effect shows one frame of the wrong scheme.

Light mode was real work, not a flag. The sheet had **30 hardcoded
`rgba(255,255,255,…)` overlays** that would have rendered white-on-white, and
**52 hardcoded semantic tints** derived from dark-mode hues. Both are gone:
overlays now come from one `--fill-1…5` ladder (white over dark, black over
light), and the tints are `color-mix(in srgb, var(--token) N%, transparent)`,
so they follow whichever palette is live.

**Contrast was measured, not eyeballed** — necessary, since these changes were
made without being able to see the page. Every light-mode pair clears WCAG AA
(4.5:1) on white: text 15.05, supports 5.59, discounts 4.80, contradicts 5.38,
accepted 5.08, tests 7.33, and white-on-accent 5.08. Apple's own light
secondary grey (`#8e8e93`) measured **3.26:1** and failed for the small
metadata it is actually used on, so `--text-dim`/`--text-faint` were darkened
to `#5a5a61`/`#717177` (6.84 / 4.85) rather than shipped as-is.

**The light palette is written twice** — once in the media query for "system",
once under `:root[data-theme="light"]` for an explicit choice — because CSS
cannot share a declaration list between the two and a preprocessor would be a
build step this project does not need. `tests/test_ui_theme.py` (5 tests) is
what keeps that honest: it asserts the two palettes have not drifted (39 tokens
each, compared name by name and value by value), that every light token has a
dark default on `:root` (a token defined only for light would resolve to
nothing in dark), that no hardcoded white overlay has crept back into the sheet
body, that all three theme states are reachable, and — design.md §10 — that
discounting edges still differ from supporting ones in dash pattern *and*
weight and that `contradicts` keeps its weight, in the graph *and* in the
legend. A restyle must not quietly reduce those to a colour difference.

---


## UI defect pass and responsive design

**Update: UI defect pass + responsive design.** Seven reported problems, all
fixed; three were the same class of bug — a colour hardcoded for dark mode.

**Light-mode breakage (the theme pass missed these).** `.tab.on` set
`color: #fff` over `--bg-elevated`, which is `#ffffff` in light: the active
tab's label was white on white. The selected graph node hardcoded
`fill: #22262e`, turning the box dark and its text invisible; hover reused
`--bg-elevated`, which equals the node's own base fill in light, so hover did
nothing. Node surfaces are now three tokens (`--node-fill`, `-hover`,
`-selected`) defined per scheme.

**Graph: same-column edges were drawn straight through the node boxes.**
`edgePath` had no same-column case, so those fell through to the backward
branch and rendered as a horizontal line from the source's left edge to the
target's right edge — through both nodes and everything between them. This was
not cosmetic: `parallel_of`, `descends_from` and `contradicts` all connect
nodes *within* one column, so the three edge types that carry the design's
actual argument were exactly the ones being drawn as lines through solid
rectangles. They now bow out into the column gap, further for a longer vertical
span so several stay separable, and `COL_GAP` widened to 310 to make room.
Verified by running the real layout: the path starts on the node's right edge,
bows outward, and stays clear of the next column.

**Graph: titles overflowed the node.** Truncation was by character count
(`24`), but CJK is full-width — 24 Chinese characters at 13px is ~312px in a
164px slot, so most titles on this corpus spilled out. Replaced with
`fitText()`, which budgets in pixels (full-width ≈ 1em, Latin ≈ 0.53em), plus a
`clipPath` on every node as the hard guarantee behind the estimate. The Heart
Sutra title now cuts at 12 characters instead of 24.

**Controls: one radius and one height.** Buttons ranged from 7px to a 999px
pill and stood at 28/31/31/34px in the same row, which read as four unrelated
widgets. Now `--radius-control` / `--radius-control-inner` and `--control-h`
(top bar) / `--field-h` (forms), set as explicit heights rather than left to
padding plus line-height. Pills stay pills where a pill is the right shape
(badges, chips, the round close button); `.btn.tiny` is the one documented
height exception, since an inline row action must not be form-control tall.

**Stats collapsed into a disclosure** (`StatsBar.jsx`): the two totals a reader
tracks, with the per-type breakdown one click away. Ordered by the evidence
chain rather than by count, so the list matches the graph's columns. Only one
popover opens at a time — two overlapping panels in one corner reads as a bug.

**The gear was off-centre**: the hand-traced path carried a
`translate()/scale()` on the outer shape only, so the ring sat off the hub.
Rebuilt from computed geometry, everything concentric on (8,8).

**Responsive design, five stages, each driven by a specific failure** rather
than by round numbers: 1180px (410px of inspector over a 1000px viewport hides
the graph → narrower), 940px (overlaying beats stacking only while two node
columns fit → bottom sheet; the tagline goes), 760px (the top bar needs ~740px
for brand + 3 tabs + stats + refusals + gear → two rows, tabs full width),
560px (reading columns stop being two-up; stats collapses to one figure, since
dropping the words but keeping both would read as "37 43"), plus short-viewport
rules for landscape phones. `@media (pointer: coarse)` raises control heights
to 36/44px — keyed off the pointer, not the width, because a large tablet is
still a thumb.

The graph SVG is deliberately *not* responsive: its layout is deterministic and
citable (graph-model.js), so it scrolls inside its pane rather than reflowing
into a different picture at every width.

**Contrast re-measured after every colour change.** The tinted selected-node
fill dropped the small type/status labels to 2.66:1 (dark) and 4.17:1 (light);
one step up the grey ramp restores 5.23 / 5.88 without letting them compete
with the title.

---


## Stage-4 tools registered, and the UI can run a swarm

**Update: the stage-4 tools are registered, and the UI can run a swarm.** The
two remaining gap-analysis items, plus one defect the live run exposed.

**1. `link_parallels` and `collate_editions` are now agent tools.** They had
been withheld because a wrong `parallel_of` edge *suppresses* independent
support and edges have no retraction. What settles it: **neither tool takes a
judgement as input.** Both accept only a `witness_id`; the content comes from
the corpus's own `<cb:docNumber>` and `<app>` markup, and `link_parallels`
already refuses `cf.`/`Part of` references, ambiguous Taisho resolutions and
witnesses absent from the graph. The model chooses *what to read*, not *what is
true* — the same discretion `find_attestations` always had. `PROMPT_VERSION` →
`attestation_worker/v5-stage4-tools`; the system prompt now also states that a
`parallel_of` edge *reduces* support, so recording one is describing the
evidence correctly rather than weakening it.

**2. A run is now one or several agents.** `RunManager` takes a list of
`AgentSpec`s and drives `run_swarm()`; `POST /api/run` accepts either the
single-agent shape or `{agents: [...]}`. The UI grows an agent card per worker
asking for **corpus scope** and **method** — real research commitments, not
personas (roadmap.md, "viewpoint formation without persona theater"). Bounded
at 4 agents: past a handful the count starts being the claim rather than the
mechanism, which design.md §9 lists as an anti-goal.

Four properties, all tested: several agents share **one** graph, **one** lock
and **one** budget (three caps would mean the number the researcher typed bound
none of them); every tool call is attributed to the agent that made it; one
agent's transport failure is reported against that agent instead of failing the
run; and ids must be distinct, because ids are how contributions are attributed.
`run_swarm()` gained optional `on_tool_call(worker, entry)`/`should_stop` —
passing progress *outward* to one observer is not agent-to-agent messaging, and
no worker can see another's callback, results or transcript (§5 principle 3).

**Live-verified**: two agents with distinct declared scopes, $0.00336, 62.8s,
16 model calls, genuinely interleaved (`heart-sutra=6 apparatus=2` mid-run), and
`link_parallels` and `collate_editions` both reached by a real model for the
first time.

**3. The defect that run exposed.** Eight of those sixteen calls were refused,
and none of the refusals was avoidable: `find_attestations` returned only
*passage* ids while the stage-4 tools take a *witness* id, so the agents guessed
— `B01n0001`, `B01n0001_002`, the passage id — and were correctly refused each
time until one stumbled onto `witness:B01n0001`. That is a gap in the tool, not
a model mistake, and the same shape as the missing `propose_claim`.

`find_attestations` now returns a `FindAttestationsReport` with `passages` **and**
`witnesses` (deduplicated — several hits routinely land in one witness), and its
description tells the agent to pass those ids on and never construct one.
Verified deterministically against the real archive rather than by paying for
another run: 3 passages → 2 witnesses, and both stage-4 tools accept
`report.witnesses[0]` verbatim with zero refusals (232 apparatus entries
collated, joint sigla not split).

**One honest note on that verification.** The confirming *live* run failed
before reaching `link_parallels`: OpenRouter returned a malformed response
(`OpenRouterError: Invalid OpenRouter response`). The failure paths behaved
correctly — the error was isolated to that agent and surfaced with its reason,
the run was marked `failed` rather than silently finished, and the unpriced
response was **charged** $0.01 as an estimate rather than treated as free, which
is exactly what `budget.py` documents. But it means the end-to-end no-guessing
path is proven deterministically, not live.

---
