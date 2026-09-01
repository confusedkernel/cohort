# cohort

Evidential pluralism made auditable — a supervised evidence graph for
multi-agent textual research.

Agentic research systems usually import their verification model from
fact-checking: many sources agreeing raises confidence. Transmitted textual
corpora violate the independence assumption that model needs, because agreement
between witnesses is usually evidence of shared descent rather than independent
confirmation. COHORT is an evidence graph in which nothing is asserted as true,
relations of descent and parallelism are first-class, claims must cite their
sources, conjectures must arrive with what would refute them, and only the
researcher can promote a finding to citable status.

See `DESIGN.md` for the design, `ROADMAP.md` for structure, tech stack and
build order, and `HANDOFF.md` for current state and next steps (start there if
you're picking this up fresh, e.g. on a different machine).

## Access governance is a separate system, and it is not connected

COHORT has **no** access-governance layer. There is no policy file, no
allowlist, no request caps, no retention rules and no deletion verification, and
nothing here should be read as providing any of them. That work belongs to
ATELIER, which is a separate working system, currently **not** integrated —
COHORT's `search`/`fetch` source interface is deliberately shaped like
ATELIER's adapter so that integration later means writing one adapter class,
but that integration has not happened.

What COHORT does do about rights is narrow and worth stating exactly: the
development corpus (CBETA v061) is locally held and licensed
CC BY-NC-SA-equivalent, not public domain, so its terms are carried through
every derived artifact — `source_terms` on every witness node and in every
corpus API response — rather than dropped. Corpus bytes are never committed to
this repository; only a local path is configured. That is provenance hygiene,
not governance, and it is not a substitute for it.

## Quickstart

No corpus, no API key, no network needed:

    python -m venv .venv && .venv/bin/pip install -e '.[dev]'
    .venv/bin/pytest -q
    .venv/bin/python demo.py

`demo.py` prints the thing worth seeing first: a claim whose support count
stays at two while its independence flag flips to false the moment a
`parallel_of` edge is recorded. That is the counter-argument to
consensus-seeking, in three lines of output.

## The researcher UI

    .venv/bin/pip install -e '.[ui]'
    cd cohort/ui/frontend && npm install && npm run build && cd -
    .venv/bin/python scripts/seed_demo_graph.py     # needs the corpus
    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite

Reads never take the writer lock, so the UI can serve while an agent run is
writing. Three capabilities are opt-in separately, because they carry different
consequences — reading the corpus is free, accepting a finding is a scholarly
act, and starting an agent run spends money:

    --corpus        corpus browse/search
    --allow-writes  the researcher's accept / reject / reopen
    --allow-runs    the agent-run launcher   (--max-budget caps each run)

It binds `127.0.0.1` by default and deliberately: the corpus behind the graph is
license-restricted. Over SSH, forward the port rather than changing the bind.

## Live scripts

Everything under `scripts/` that calls a model is **manual-only and never run
by the test suite**. Each one names its own cost in its docstring. Spend is
capped in code (`cohort/agents/budget.py`) rather than estimated: the cap is
checked *before* a request, and a response that reports no cost is charged an
estimate rather than treated as free.

Corpus access needs `CBETA_ARCHIVE_PATH` and a built index
(`scripts/build_cbeta_index.py`); see `.env.example` and `HANDOFF.md`.

## Conventions

No linter or formatter is configured; match the surrounding style. The house
habit that matters most: **a document about this system should report
arithmetic, not assertion** — count the outputs rather than claiming things
about them. If a rule in `DESIGN.md` cannot be honoured, say so and stop rather
than quietly working around it.
