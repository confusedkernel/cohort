# Decisions

Decisions that shaped the system, and the ones that were **reversed**. A
reversal is recorded with what was believed, what changed it, and what the wrong
belief cost — the house rule is that a superseded conclusion says so rather than
going quiet.

Narrative order is in [changelog.md](changelog.md). This is the index.

## Standing constraints

Not up for renegotiation without the researcher's say-so.

| Constraint | Source |
|---|---|
| **Corpus bytes are never committed.** Only a local path is configured. | [design.md](design.md) §2 rule 1 |
| **Claim no governance.** No retention, rights-aware or deletion language while ATELIER is unplugged. | [design.md](design.md) §2 rule 2 |
| **Live scripts are manual-only**, never automated by the test suite. | [cli.md](cli.md) |
| **API spend is capped in code**, checked before the request, not estimated after. | [agents.md](agents.md) |
| **Never paste a real API key into a chat session.** | — |
| **The chronology scheme is not to be decided unilaterally.** | [design.md](design.md) §14 |
| **When a design rule cannot be honoured, say so and stop.** Do not implement something that looks like it honours the rule. | [design.md](design.md) §0 |

## Decisions that held

**The event log is ground truth; SQLite is a projection.** Rebuild-and-diff
asserts it. This is what made three schema migrations safe.

**Tools are the only writers.** A rule in a prompt is a request; a rule at the
write boundary is a property. Every rule the design claims has one exception
class and one enforcement site.

**Agents communicate only through the graph.** No messaging, no shared
transcript. Linear rather than quadratic cost, every contribution attributed,
and the whole shared state is one inspectable object.

**Node identity comes from the source, never from hashing agent text.** Two
agents finding the same passage converge on one node with two authorship
records. Hashing agent output into identity would fragment the graph silently —
making the system look more productive as it became less correct. Payload
hashing exists, but for integrity only.

**The vocabulary stays closed.** Four types were added across five stages
(`part_of`, `verifies`, `searched_for`, `verification`), each with its argument
recorded. That is the discipline being exercised, not abandoned.

**No client library for the model layer.** OpenRouter over stdlib `urllib`. The
tool layer is already the constraint surface, so a framework would add machinery
the design doesn't need. This *replaced* an earlier decision to use the plain
`anthropic` SDK behind an optional `agents` extra — the extra never shipped, and
the conclusion it protected (no LangChain, no Agent SDK) is unchanged.

**`indeterminate` and `unknown` are real answers.** A verification may conclude
nothing; a witness may be undated. Both still owe a stated reason.

## Reversals

### Edges can be withdrawn after all
**2026-09-02.** "Edges have no ladder and no retraction, so a wrong edge is
permanent" was recorded here as a deliberate deferral, mitigated by tools
refusing ambiguous input. Comparing against `epistemic-swarm` made the deferral
untenable: a mistaken `parallel_of` does not add noise, it *suppresses*
independent support that genuinely exists, silently and in the direction of this
project's own thesis. Retraction is now built (migration 4) on the same terms as
rejecting a node — researcher only, a reason required, persists against
redrawing, nothing deleted.

### Several agents on one model was not viewpoint diversity
**2026-09-02.** The scope revision allowed more agents "conditioned on
demonstrating declared viewpoint diversity", and the run launcher told the
researcher that two agents' disagreement "means something". That was false while
both ran the same model: shared training priors make their agreement one
observation reported twice — the error `independent_support()` exists to catch
between witnesses, committed one layer up between readers. A run whose agents
share a model family is now refused at the boundary. Credit where due: this is
`epistemic-swarm`'s rule, found by comparing against it.

### Agent count may grow — conditionally
[design.md](design.md) §4 and §9 called fan-out a non-headline and agent count an
anti-goal. **Superseded** after comparing against a parallel project: more
agents are allowed *when they demonstrate declared viewpoint diversity* —
distinct corpus scope and method per agent — never because a bigger number is
itself the claim. The UI caps a run at 4 for exactly this reason.

### CBETA qualifies as "locally-held"
[design.md](design.md) §2 rule 1 said "public-domain or locally-held".
**Clarified, not relaxed**: read disjunctively, locally-held qualifies on its
own, provided the real licence terms are preserved through every derived
artifact — which is why `source_terms` rides on every witness node and every
corpus API response. Rule 2 is untouched.

### A writing UI does *not* have to hold the lock
**This was wrong, and it blocked a feature for a whole phase.** The belief: an
accept/reject UI would hold the exclusive writer lock for as long as a browser
tab was open, stopping every agent run. The correction: a write takes the lock
for **one request**, not one session. Once seen, the endpoints were built in an
afternoon; a run holding the lock yields 409 with a stated reason, and
single-writer discipline is unchanged rather than relaxed.

### Refusals were only half-recorded
The system's most distinctive claim — [design.md](design.md) §15, "its refusals
are part of its scholarly output" — held only for write-boundary rules.
Lookup failures raised `NodeNotFound` directly and left **no trace in the log**,
so the single most interesting refusal (an agent inventing a node id) was
invisible. Fixed with `Graph.log_refusal()`, idempotent via a
`logged_to_event_log` flag.

### `propose_claim` was missing
Agents could attest claims but not create them. A live conjecture run exposed
this the hard way: the agent **fabricated node ids five times** trying to attest
a claim that didn't exist. Every refusal was correct; none was avoidable. The
gap was in the tool layer, not the model.

### `find_attestations` returned too little
It returned passage ids only, but the stage-4 tools take a *witness* id — so an
agent that had just called it had no way to get one and **guessed four times in
a row**. Same shape as the above, found the same way: a live run, correct
refusals, an unavoidable dead end. Now returns `passages` **and** `witnesses`.

### The stage-4 tools are safe to register
`link_parallels` and `collate_editions` were withheld because a wrong
`parallel_of` edge *suppresses* independent support and edges have no
retraction. What settled it: **neither takes a judgement as input.** Both accept
only a `witness_id`; the content comes from the corpus's own markup. The model
chooses what to read, not what is true.

## Open

**The chronology scheme.** For translation material, translation date,
composition date and recension date are three different things, and the
translator matters more than the dynasty. What replaces political-dynasty
periodization is the researcher's call — coordinate with CWN.dia, which has the
same problem in a different corpus. **Flag it, don't guess.**

**The name.** `cohort` is taken on PyPI by an MIT electromagnetics simulator,
which doesn't matter for an internal project and would matter for a published
one. Do not backronym it.

## Deferred, with reasons

| Item | Why it's deferred, not forgotten |
|---|---|
| Reputation scoring | The objection is to what a score would reward, not to when agents run. Concurrency didn't change it. |
| Relevance ranking | Corpus order is stated honestly; a list that looked ranked but wasn't would misrepresent which witnesses matter. |
| Claim versioning | Real gap. A claim can be rejected and reopened, but not revised into a new version with typed lineage — `epistemic-swarm` does this and we don't (compare.md §4.2). |
| `descends_from` extraction | **Blocked, not deferred**: no corpus channel asserts descent. |
| Automatic cross-witness contradiction | **Blocked**: needs locus alignment COHORT doesn't have and doesn't claim. |
| `<note type="cf*">` channel | ~31,800 occurrences, unread. Noted rather than quietly omitted. |
| ATELIER integration (stage 6) | Not needed yet. The seam is already one function signature wide. |
