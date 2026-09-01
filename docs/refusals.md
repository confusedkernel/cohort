# Refusals, and how to read them

COHORT's most distinctive output is not a set of findings. It is a set of
**refused writes**: things an agent tried to record and the graph declined,
each named with the rule that declined it ([design.md](design.md) §15).

Refusals are cheap to produce and easy to ignore. A flat list of forty answers
no question a researcher actually has — the question is always *which of these
should I read?* That is what the census is for.

    cohort refusals --census
    GET /api/refusals        → the same object under `census`

## What a refusal indicts

Every rule in [errors.py](../cohort/errors.py) carries a category. The category
is not severity; it is **what to go and look at**.

| Category | Meaning | What it tells you |
|---|---|---|
| `evidence` | the corpus did not support it | go and look at the **texts**. The falsifiability gate lives here: a conjecture with no refuting query, a claim with nothing citing it. |
| `standing` | who was writing, or the node's state, forbade it | the **discipline held**. An agent tried to sign its own work, skip a rung, or relitigate something settled. |
| `expression` | the writer could not say what it meant | **read these.** A reference that does not resolve, a malformed argument, a relation outside the vocabulary. |
| `operational` | the system's own preconditions | rarely reaches the log; most are raised before a write is attempted. |
| `unclassified` | a rule this version's taxonomy does not know | reported, never dropped — a census that silently ignored what it could not classify would understate the thing it counts. |

The taxonomy cannot rot: `tests/test_refusal_census.py` fails if a
`CohortError` subclass has no category, and fails again if a category names a
rule that no longer exists. Adding a rule means deciding what it indicts, the
same discipline `tests/test_parity.py` applies to the two front ends.

## Streaks — the signal worth acting on

A **streak** is a run of refusals from one agent, against one rule, with
nothing else of its own in between.

One `expression` refusal is usually a model slip. A *run* of them is the shape
of something else: the agent adapted, tried again, and was refused again,
because there was no sanctioned way to say what it meant. **Every streak in
this project's history so far turned out to be a gap in the tool layer, not a
model error** — and each one became a tool fix. See
[changelog.md](changelog.md): a missing `propose_claim`, witness ids the tools
never returned, a claim its own author could not advance.

Streaks are consecutive **within one author's own sequence**, not within the
whole log. Several agents interleave their refusals in one run, and a
definition broken by an unrelated agent's refusal landing in between would lose
the signal exactly when the most agents are running.

`node_ids` is the strongest tell inside a streak. Several *distinct* ids under
one rule means the agent was guessing:

    2 streak(s), 7 of 10 refusals — one agent refused repeatedly by one rule.
      4x NodeNotFound [expression] by agent:apparatus calling collate_editions (#120-128)
          tried: passage:A098n1267#…, passage:A114n1505#…, A098n1267#… +1 more
      3x NodeNotFound [expression] by agent:heart-sutra calling link_parallels (#101-118)
          tried: B01n0001, B01n0001_002, passage:B01n0001#…

That is the demo graph's own log, and it is the historical record of a real
defect: `find_attestations` returned only *passage* ids while the stage-4 tools
take a *witness* id, so two agents guessed and were correctly refused until one
stumbled onto the right shape. The census finds it mechanically, from the log,
with no annotation.

## What the census does not do

**It counts; it does not conclude.** Nothing here decides that a tool is
missing — that is a judgement, and the point of counting is to put it in front
of someone who can make it. The category says which bucket to look in and a
streak says where to look first; both are evidence for a reading.

A zero is a fact, not an absence of news. A run that refused nothing is a real
result about that run.

## Where the numbers come from

`summarize_refusals(log_path)` is a pure log scan, like
`summarize_model_calls`. It takes a path rather than a list so a caller cannot
accidentally census a truncated view: `read_refusals(limit=n)` returns the
tail, and a census over the tail would report a smaller total than the log
holds while looking authoritative.

A refused write changed no graph state, so there is nothing in the SQLite
projection to read any of this from — which is also why the census survives
`rebuild()` unchanged. The log is ground truth.

Note that `NodeNotFound` raised by a *lookup* never reaches the write boundary,
so it is recorded through `Graph.log_refusal()` at the tool boundary instead.
Both paths land in the same log and the census does not distinguish them; the
live conjecture run that lost five refusals to the gap between them is why
`log_refusal()` exists at all.
