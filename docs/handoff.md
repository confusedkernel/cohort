# Handoff: current state

What is true as of **2026-09-02**. For how the system got here, see
[changelog.md](changelog.md); for why it is shaped this way, see
[design.md](design.md).

## Read first

1. **[design.md](design.md)** — the design spec. Its §0 carries a standing rule
   that governs everything else: *"when a rule here cannot be honoured, say so
   and stop. Do not implement something that looks like it honours the rule."*
   Follow it literally. The predecessor project's central failure was
   documentation describing guarantees the code did not provide.
2. **[roadmap.md](roadmap.md)** — structure, tech stack, build order, and the
   "Scope revision" section recording every deliberate departure from the
   original design text, each quoted and annotated in place rather than
   silently changed.
3. **This file** — what exists, what doesn't, and what's left.

## Verified state

    .venv/bin/pytest -q      # 390 passed
    .venv/bin/python demo.py # no corpus, no API key, no network

Proven by real runs rather than by assertion — every one manual, none
automated: a live OpenRouter call; two *concurrent* live agents writing to one
graph; attestation against the hash-verified CBETA archive; the stage-4
`parallel_of` flip on three real Heart Sutra translations; a conjecture through
the falsifiability gate with a real prior-art search ($0.004); an agent run
started from the browser ($0.00236); a two-agent swarm started from the browser
($0.00336, 62.8s, 16 calls, interleaved); and a **three-model run with a
reviewer, then censused** ($0.00402, 12 calls, `z-ai` + `deepseek` + `qwen`) in
which one claim was promoted and one was withheld on the reviewer's reading
with all ten of its citations re-fetching cleanly. Rebuild fidelity and payload
integrity are re-checked after each live run, not assumed — that one replayed
95 events to 40 nodes / 45 edges with 0 mismatched payload hashes.

## What exists

- **The write boundary.** Closed vocabulary, append-only event log as ground
  truth, SQLite projection, rebuild-and-diff fidelity, single-writer
  discipline. See [architecture.md](architecture.md) and
  [vocabulary.md](vocabulary.md).
- **Verification and assurance.** `Graph.verify()`, `assurance_for()`, five
  methods, A0–A4 as a computed read, plus independent payload-integrity
  hashing (`verify_integrity()`).
- **Two corpus readers.** `LocalReader` (manifest-driven plain text, used by
  every test) and `CbetaReader` (hash-verified archive access, TEI
  header-skipping, unique-span excerpt location). See [corpus.md](corpus.md).
- **Six worker tools** behind `AttestationWorker`, plus `run_swarm()` for real
  concurrent multi-agent execution and a spend cap enforced in code. See
  [tools.md](tools.md) and [agents.md](agents.md).
- **A reviewer role.** `ReviewWorker` and `review_claim`: an agent may not
  attest what it authored, nor what an agent on its own model family authored,
  and the reviewer's judgment can withhold promotion but never supply it.
- **The refusal census.** `summarize_refusals()` over the event log: counts by
  rule, by category and by author, plus streaks — one agent refused repeatedly
  by one rule, which is the shape of a tool gap rather than a model error. On
  both front ends. See [refusals.md](refusals.md).
- **Two front ends with the same capabilities.** The `cohort` CLI and the web
  UI cover the same set — graph, provenance, findings, refusals, integrity
  checks, accept/reject/reopen, corpus, agent runs — and `tests/test_parity.py`
  fails if one gains something the other lacks. See [cli.md](cli.md) and
  [ui.md](ui.md). The UI's capabilities are each opt-in behind their own flag.
- **Agent identity.** `register_agent`, `AgentProfile`, and `agent_report()` as
  a pure contribution count — deliberately not a reputation score.

## What does not exist

Each of these is a deliberate position, not an oversight. Say so plainly rather
than implying coverage.

- **Relevance ranking** over search results. Results come back in corpus order
  and every response says so. A list that looked ranked but was not would
  misrepresent which witnesses matter most.
- **`descends_from` extraction.** Nothing in the markup asserts descent
  directly, so there is no corpus channel for it. `parallel_of` is what the
  corpus actually states, and that is built and live-verified.
- ***Automatic* contradiction detection across witnesses.**
  `record_contradiction` writes the edges, but *finding* disagreements needs
  locus alignment between witnesses — knowing that passage A here and passage B
  there are the same place in the text — which COHORT does not have and does
  not claim. Apparatus markup cannot supply it either: it describes variants
  within one document.
- **What a reviewer cannot check.** The cross-model reviewer, previously the
  top item here, **is now built** — `ReviewWorker`, `review_claim`, and the
  `SelfAttestation`/`ReviewerNotIndependent` rules at the write boundary (see
  [agents.md](agents.md), [vocabulary.md](vocabulary.md)). What it does *not*
  do is adjudicate meaning: promotion rests on re-fetched spans, and the
  reviewer's judgment can only withhold. A claim whose citations re-verify
  perfectly but which reads more into them than they say will pass unless the
  reviewer objects, and its objection is recorded rather than enforced. That
  is deliberate — `VerificationMethod` refuses `MODEL_ENTAILMENT` for the same
  reason — but it means "attested" still means "cited and located", never
  "true".
- **A named-but-unreachable assurance rung.** *Resolved 2026-09-02, and the
  note that stood here was wrong twice over.* It claimed no verification
  method yields A3; `collate_editions` does, via `CROSS_EDITION_COLLATION`.
  The real problem was that the rung was called `A3_INDEPENDENCE_CHECKED`
  while the only check reaching it established edition support within one
  document — so the tool carried a standing `limitations` paragraph
  disclaiming its own grade. Renamed to `A3_EDITION_SUPPORT_CHECKED`;
  cross-witness independence stays a live computed read and is deliberately
  ungraded. See [vocabulary.md](vocabulary.md).
- **Model family is a provider prefix.** The independence floor cannot catch
  the same weights served under two provider names, and an agent that never
  registered a model is not checked at all. Stated in `cohort/families.py`,
  repeated here so it is not mistaken for a guarantee.
- **Formulaic shared passages would count as descent — but nothing can draw
  such an edge yet.** *Corrected 2026-09-02: this was logged as a live gap and
  is not one.* `independent_support()` does flip `independent` to `False` on
  *any* `descends_from`/`parallel_of` edge with no notion that a shared stock
  opening is not evidence of descent. But `link_parallels` is the only writer
  of `parallel_of`, and it writes only CBETA's own **asserted**
  `<cb:docNumber>` cross-references — a curatorial statement that two texts
  are parallel translations, not an inference from shared text. Nothing writes
  `descends_from` at all, and neither front end can draw an edge by hand. So no
  boilerplate passage can currently create a false descent link.

  It becomes a real gap the moment COHORT gains shared-passage detection, which
  is what `descends_from` extraction (above) would need. The third sibling has
  the problem precisely because its descent links *are* mechanically detected
  overlaps: it reported 100 of 146 links excluded as colophon or stock opening,
  the shared text among its witnesses being dominated by the attribution
  colophon itself. **Build the exclusion in the same change as the detector,
  not after** — see compare.md §10.
- **No deterministic measurement layer.** Tools return spans; agents compute
  everything themselves and can therefore miscount. Both sibling projects now
  measure first and let models only interpret and cite the measurements —
  `epistemic-swarm` with a census worker, the third with an evidence table whose
  ids are the only citable objects. Arrived at independently by both, which is
  the strongest signal in compare.md §8.
- **Claim versioning.** A claim can be rejected and reopened but not revised
  into a new version with typed lineage, the way `epistemic-swarm` does it.
  Corrections are therefore coarse. (Edge retraction, previously listed here,
  **is now built** — see [vocabulary.md](vocabulary.md).)
- **The `<note type="cf1|cf2|cf3">` channel** — 436 occurrences in the
  300-file sample, ~31,800 corpus-wide. Only `<cb:docNumber>` is read so far.
- **Reputation scoring** (agent-society step 5) — deferred deliberately.
  Concurrency didn't change the reasoning: the objection is to what a score
  would reward, not to when agents run.
- **Access governance.** No policy file, no allowlist, no caps, no retention
  rules, no deletion verification. That is ATELIER's job and it is **not
  connected**. See [design.md](design.md) §2, whose rule 2 forbids claiming
  otherwise.
- **ATELIER integration** (stage 6) — not started, not needed yet.

## Environment

    python -m venv .venv && .venv/bin/pip install -e '.[dev]'
    .venv/bin/pytest -q
    cp .env.example .env

Then fill in `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` by hand. **Never paste
a real key into a chat session.** `CBETA_ARCHIVE_PATH` is needed for anything
touching the real corpus; see [corpus.md](corpus.md).

Every runnable entry point, with its cost and prerequisites, is in
[cli.md](cli.md).

Venvs bake in absolute paths: if this repo moves, delete and recreate `.venv`
rather than reusing a copy from elsewhere.

## What's left

1. **The paper.** [design.md](design.md) §15 has the claim paragraph and the
   venue is PNC 2026, but no submission artifact exists in this repository.
   This is the largest remaining piece of work and it is not a coding task.
2. **The chronology scheme — do not decide it unilaterally.** Named as open in
   [design.md](design.md) §14 for a reason: for translation material,
   translation date, composition date and recension date are three different
   things, and the translator matters more than the dynasty. Flag it, don't
   guess.
3. **`record_contradiction` has never been called by a live model.** Every
   other registered tool has. One cheap run would close that gap.
3b. **Done, 2026-09-02.** Three live three-model runs with a reviewer, censused.
   The first two each found a defect in the census's own reach — nine tool rules
   raising bare `ValueError`, and an id listing whose `claim:` prefix all three
   models read as a label — and the third came back clean. See
   [refusals.md](refusals.md) and [changelog.md](changelog.md). What is still
   missing is a *negative control*: nothing has yet shown the system catching a
   citation that does not re-verify, only one whose reviewer disagreed with what
   the citations were taken to show.
4. **A measured scaling study.** Scaling still rests on one two-agent run;
   `epistemic-swarm` publishes a four-point table. Needs live API calls.
5. **A self-hosting position.** OpenRouter is still the only model path — see
   compare.md §8.
6. **Deferred and fine to leave**: ATELIER integration, reputation scoring,
   relevance ranking. Each is described above.
