# Refusals, and how to read them

COHORT's most distinctive output is not a set of findings. It is a set of
**refused writes**: things an agent tried to record and the graph declined,
each named with the rule that declined it ([design.md](design.md) §15).

Refusals are cheap to produce and easy to ignore. A flat list of forty answers
no question a researcher actually has — the question is always *which of these
should I read?* That is what the census is for.

    cohort refusals --census
    cohort refusals --run 1c0a47ba0b67 --census    # one run, not the graph's whole life
    GET /api/refusals[?run_id=…]                   → the same object under `census`

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

The taxonomy cannot rot. `tests/test_refusal_census.py` fails if a
`CohortError` subclass has no category, fails again if a category names a rule
that no longer exists, and fails a third time if any tool raises something the
census cannot name. Adding a rule means deciding what it indicts, the same
discipline `tests/test_parity.py` applies to the two front ends.

That third guard exists because the first two missed something. The first live
multi-model run to be censused (2026-09-02) returned one refusal and it came
back `unclassified`: `propose_claim` refused an ungrounded claim — the design's
flagship evidence refusal — as a bare `ValueError`. Nine such raises were
spread across the tool layer, so a reviewer barred from a claim, a mistyped id
and a claim the corpus would not support all arrived under one meaningless rule
name. They are now `UngroundedClaim`, `WrongNodeType`, `SourceRefMissing` and
`InvalidVerdict`, and `review_claim` re-raises the reviewer conflict *as
itself* rather than wrapping it, so `SelfAttestation` and
`ReviewerNotIndependent` keep the names the census counts by.

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

## The first live census, in three runs

The census was built and tested against the demo log before it had ever seen a
fresh run. On 2026-09-02 it saw three, each two workers and a reviewer on three
distinct model families (`z-ai`, `deepseek`, `qwen`), roughly $0.003 apiece.

**Run 1 — one refusal, `unclassified`.** `propose_claim` refused an ungrounded
claim as a bare `ValueError`. That is the finding above: the tool layer raised
nine unnamed rules, and the census reads rule *names*.

**Run 2 — 12 refusals, and a streak of five.** With the rules named, the
picture resolved: 5 `UngroundedClaim` (`evidence`) and 7 `NodeNotFound`
(`expression`), the largest streak being **all five of the reviewer's reviews,
refused in a row**. Every one had dropped the `claim:` prefix from the id it
was handed. So had the second worker, twice, on ids `propose_claim` had just
returned it. Three models on three families making the same mistake is not
three coincidences — it is the streak metric's premise, and here it held across
families rather than within one agent.

The cause was ours. `pending_review_context` listed each claim as
`- claim:abc… [claim] '…'`, in which `claim:` reads as a field label and the
uuid as its value. The prefix is now quoted and named as part of the id, and
`Graph._unfound_detail` makes the refusal teach: an id with no prefix that
matches exactly one node comes back *"did you mean `claim:abc…`? An id carries
its type prefix"*. The malformed id is still refused — repairing it silently
would teach that the type is decoration — but the dead end became a correction.

**Run 3 — zero refusals**, both claims reviewed, 95 events replaying to 40
nodes and 45 edges with 0 mismatched payload hashes. A zero is a fact: this one
says the two fixes landed.

> Run 2's event log was overwritten by run 3 and is gone. The counts above come
> from its console transcript, and the defect itself is now pinned by tests
> rather than by that log. Keep the `.jsonl` of a live run before starting the
> next one — `scripts/run_negative_control.py` now refuses to clobber one
> without `--force`, for exactly this reason.

Since then a run is an event, so a census can be taken of *one run* rather than
of a graph's whole life: `cohort refusals --run <id>`. The whole-log view is
still the right one for reading history; the per-run view is the one a
comparison between runs needs. See [architecture.md](architecture.md).

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
