# Vocabulary reference

The node and edge vocabulary is **closed on purpose** — small enough for one
slide. A vocabulary that grows whenever something doesn't quite fit becomes an
ontology project. *Adding a type requires an argument*
([design.md](design.md) §6, §9).

Everything below is the vocabulary as enforced in `cohort/schemas.py` and
`cohort/graph.py`, not as originally proposed. The design doc's §6 tables
predate `part_of`, `verifies`, `searched_for` and the `verification` node; each
addition is annotated there.

## Nodes — 7 types

| Type | Meaning | Payload (required / optional) |
|---|---|---|
| `witness` | a text as transmitted: an edition, a recension, a manuscript | `canonical_ref`, `dating` / `label`, `source_terms` |
| `passage` | a located span within a witness | `canonical_ref`, `locator` / `excerpt`, `source_ref` |
| `claim` | an assertion that must cite passages | `text` |
| `conjecture` | an assertion allowed to exceed its evidence, if testable | `text`, `derivation`, `corpus_boundary`, `selection_risks`, `alternative_explanations` |
| `query` | a retrieval that was run, or that would test a conjecture | `text` |
| `decision` | a researcher judgement, kept as part of the record | `subject_node_id`, `verdict` / `reason` |
| `verification` | one verification attempt against another node | `method`, `result`, `assurance_level`, `detail` / `limitations`, `source_hash`, `excerpt_hash`, `span_start`, `span_end` |

`decision` and `verification` are **audit records, not evidence**. `citable()`
excludes both, and the UI hides them unless you turn them on.

A `conjecture`'s four extra required fields are the falsifiability dossier —
none may be blank. That, plus a `tests` edge, is what buys a conjecture the
right to exceed its evidence ([design.md](design.md) §7).

Authorship is a **field on every event, not an edge**. An `authored_by` edge
would duplicate it with no way to keep the two consistent.

## Edges — 10 types

| Type | Domain (src → dst) | Meaning |
|---|---|---|
| `attests` | `passage` → `claim`\|`conjecture` | the evidential edge |
| `contradicts` | any → any | disagreement made visible |
| `parallel_of` | `passage`→`passage`, `witness`→`witness` | shared transmission |
| `descends_from` | `passage`→`passage`, `witness`→`witness` | makes agreement non-independent |
| `quotes` | `passage` → `passage` | citation within the corpus |
| `tests` | `query` → `conjecture` | the falsifiability edge |
| `supersedes` | same type → same type | revision |
| `part_of` | `passage` → `witness` | locates a passage in its witness |
| `verifies` | `verification` → `witness`\|`passage`\|`claim`\|`conjecture` | attaches an audit record |
| `searched_for` | `query` → `claim`\|`conjecture` | the retrieval that produced it |

Domains are enforced at the write boundary; a violation is
`EdgeDomainViolation`. Edges never create their endpoints
(`EdgeEndpointMissing`) and never self-loop (`EdgeSelfLoop`).

**Symmetric on read**: `contradicts` and `parallel_of`. Both are stored in both
directions, so a query in either direction finds them — the UI de-duplicates
when drawing, or these edges would carry double their true visual weight.

**Two edges discount support rather than adding it**: `parallel_of` and
`descends_from`. This is the whole thesis in the vocabulary — see
`independent_support()` below.

## Edge retraction

Edges have no promotion ladder — but since 2026-09-02 the researcher can
**withdraw** one, with a stated reason:

    cohort retract-edge edge:abc --reason "the docNumber bracket was a cf."
    cohort restore-edge edge:abc --reason "checked again; it is a bare list"

This matters more than it sounds. A mistaken `parallel_of` does not add noise —
it **suppresses independent support that genuinely exists**, silently, in the
direction of this system's own thesis. That was previously permanent.

Retraction is the edge-equivalent of rejecting a node, so it follows §8's rules:

- **only the researcher** may do it, and a **reason is required**;
- **it persists** — `add_edge` refuses to redraw a retracted edge
  (`PersistentRetraction`), so the next `link_parallels` run cannot quietly
  overwrite the judgement. Restoring is a researcher action;
- **nothing is deleted.** The row and the log both keep it. `edges()` hides it
  by default (it asserts nothing now), `edges(include_retracted=True)` returns
  it, and the UI shows it struck through with its reason — because "the
  researcher withdrew this" and "this was never asserted" are different facts;
- **both directions move together** for symmetric edges, and each row records
  who withdrew it.

`independent_support()` ignores retracted edges, which is the whole point:
withdrawing a wrong `parallel_of` gives the support back **without changing the
count**, since the evidence never went anywhere — only the claim about its
independence.

Nodes still have no versioning, and claims cannot be corrected in place. That
remains an open gap (compare.md §4.2).

`part_of` was added deliberately in stage 2. Passage-to-witness had been a
payload field, which meant `independent_support()` read JSON out of a payload to
answer the system's central question. `searched_for` was widened in stage 3 to
accept claims as well as conjectures, when `propose_claim` gained its grounding
query.

## Status: the promotion ladder

    proposed  ──▶  attested  ──▶  accepted
        │              │
        │              └────────▶  rejected
        └───────────────────────▶  rejected

| Status | Who may set it |
|---|---|
| `proposed` | an agent wrote it |
| `attested` | a mechanical check passed — the passage exists, the citation resolves, the reference is well formed. **Agents may do this, but never to their own claim.** |
| `accepted` | **only the researcher** |
| `rejected` | **only the researcher**, and only with a stated reason |

Enforced: no rung may be skipped (`RungSkipped`); only `RESEARCHER` may
accept/reject (`NotResearcher`); rejection requires a reason
(`MissingRejectionReason`) and **persists** (`PersistentRejection`) so the next
worker along cannot re-propose what was already refused. Reopening is a
researcher action.

### The author is not the reviewer

An agent may not attest a **claim** or **conjecture** it authored
(`SelfAttestation`), and may not attest one whose author shares its model
family (`ReviewerNotIndependent`). `attest` means "the mechanical
preconditions hold", and the party with an interest in that answer is the
worst party to give it.

    graph.attest(claim_id, authored_by=author)    # SelfAttestation
    graph.attest_conflict(claim_id, author)       # the reason, without writing

| Case | Refused? | Why |
|---|---|---|
| the author attests its own claim | yes | the interested party checking itself |
| a second agent, same provider prefix | yes | a different id on one model is not a different reader |
| a second agent, another provider | no | the intended path — see [agents.md](agents.md) |
| a second agent with no model declared | no | nothing to compare; the author rule still holds |
| the **researcher** attests their own proposal | no | `accept` is already the human gate, and requiring a second human would make solo research impossible |
| the author attests its own **witness** or **passage** | no | source-derived: where a passage sits is settled by the corpus, not by judgment |
| a **query** | not reviewable | a retrieval to run, not an assertion — nothing for a second reader to be right about |

`attest_conflict()` is the public read that lets a caller decline rather than
provoke a certain refusal — `find_attestations` uses it so an author gathering
its own evidence doesn't write a predictable refusal on every call and bury the
ones worth reading.

Only `accepted` nodes are citable by output or usable as premises by other
agents. An agent cannot build on a finding the researcher has not signed.

## Assurance levels — a computed read, not a status

`assurance_for(node_id)` returns the **highest passing** level across a node's
verifications. It is derived, never stored, and never a confidence score.

| Level | Meaning |
|---|---|
| `A0_UNCHECKED` | nothing has verified this node |
| `A1_LOCATOR_VALID` | the reference resolves |
| `A2_EXACT_SPAN_MATCHED` | the excerpt was re-fetched and matched byte for byte |
| `A3_INDEPENDENCE_CHECKED` | descent/parallelism between supporting witnesses was examined |
| `A4_HUMAN_APPROVED` | the researcher signed it |

## Verification methods and results

| Method | What it checks |
|---|---|
| `locator_resolution` | the reference resolves to a real record |
| `exact_span` | the stored excerpt still matches the source exactly |
| `cross_edition_collation` | which edition families the apparatus cites |
| `dating_route_confidence` | how a date was arrived at |
| `human_review` | the researcher looked |

Results are `pass`, `fail`, `indeterminate`. **`indeterminate` is a real
answer**, not a failure — the same commitment as `unknown` dating below.

Every verification may carry `limitations`, free text stating what the check did
*not* establish. `collate_editions` always populates it.

## Dating routes

Every `witness` carries a dating record: a value that **may be null**, a
confidence, and a `basis` that must be a real sentence.

| Route | Meaning |
|---|---|
| `dated` | a date with evidence behind it |
| `attributed` | a date asserted by tradition or a catalogue |
| `source_label` | whatever the source says, carried through unexamined |
| `unknown` | no date assigned |

**Declining to date something is a legitimate answer that still owes a reason.**
`find_attestations` writes `unknown` with the basis *"not yet dated by this
worker; no dating route run"* rather than guessing or leaving the field empty.

## `independent_support()` — the thesis, as code

    IndependentSupport(node_id, attesting_count, distinct_witnesses,
                       independent, non_independent_pairs)

`independent` flips to `False` the moment a `descends_from` or `parallel_of`
edge links two of the attesting witnesses, and `non_independent_pairs` names
which. **The support count does not drop** — the evidence is still there; what
changes is the claim about its independence.

`demo.py` shows this in three lines of output, with no corpus and no API key:
a claim whose count stays at two while its independence flag goes false. That
is the counter-argument to consensus-seeking, and it is the first thing to show
anyone ([design.md](design.md) §4, §11).
