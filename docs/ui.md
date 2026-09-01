# The researcher UI

The same functionality as the Python API, in a browser. That parity is the
point: COHORT should be usable as a library by people who write Python, and as a
tool by researchers who don't.

    .venv/bin/pip install -e '.[ui]'
    cd cohort/ui/frontend && npm install && npm run build && cd -
    .venv/bin/python scripts/seed_demo_graph.py          # needs the corpus
    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite

Open <http://127.0.0.1:8000>.

## Capabilities are opt-in separately

Because they carry different consequences: reading the corpus is free, accepting
a finding is a scholarly act, and starting an agent run spends money.

| Flag | Enables |
|---|---|
| *(none)* | read-only graph, provenance, refusal log |
| `--corpus` | corpus browse and search |
| `--allow-writes` | accept / reject / reopen |
| `--allow-runs` | the agent-run launcher (`--max-budget` caps each run) |

Without a flag the routes are **not mounted at all** — a disabled capability
returns 404 rather than a 403, because the server simply doesn't have it.

It binds `127.0.0.1` by default and deliberately: the corpus behind the graph is
licence-restricted. Over SSH, forward the port rather than changing the bind.

    ssh -L 8000:127.0.0.1:8000 -L 5173:127.0.0.1:5173 you@server

## Reads never block writes

Every request opens the projection through `Graph.open_read_only()`, which takes
no writer lock — so the UI serves *while an agent run is writing*. Each write
takes the exclusive lock for **one request** and releases it; if a run holds the
lock, the endpoint answers 409 rather than waiting.

## What the graph view has to show

[design.md](design.md) §10 is a requirement, not a style guide: a naive
rendering "flattens exactly the epistemics that justify the system". If nodes
show without status and edges without the independence flag, a densely linked
node looks well supported regardless of whether its support is independent —
the visualization would silently argue *against* the thesis.

So, enforced (and covered by `tests/test_ui_theme.py`):

- **node status is a visual channel**, not a tooltip;
- **`parallel_of` and `descends_from` are visually distinct** from `attests` —
  dashed, heavier, differently coloured, and labelled "**discounts** support" in
  the legend. The API also flags them `discounts: true` so a frontend cannot
  drop the distinction by accident;
- **contradiction edges are as visible as agreement edges**;
- **clicking any node reaches its provenance** — authorship, verifications with
  their `limitations`, edges both ways, and the `independent_support` block.

Layout is a deterministic evidence chain (witness → passage → claim), not a
force simulation, which would place the same graph differently on every load —
a poor property for something meant to be read and cited.

Audit nodes (`verification`, `decision`) are hidden by default as bookkeeping
rather than evidence, behind a toggle in settings.

## HTTP API

JSON throughout. Node ids are passed as **query parameters, never path
segments**, because a passage id contains `#` (`{witness}#{excerpt}`) which a
URL path silently truncates at the fragment.

### Always available

| Route | Notes |
|---|---|
| `GET /api/health` | counts by node type, edge total, and which capabilities are on (`writes_enabled`, `corpus_enabled`, `runs_enabled`) |
| `GET /api/graph?node_type=&limit=` | nodes + edges, `limit` 1–5000 (default 500). Reports `truncated` explicitly and lists `discounting_edge_types` |
| `GET /api/node?id=` | one node with full provenance |
| `GET /api/citable` | accepted nodes only — the only ones citable by output |
| `GET /api/rejected?node_type=` | rejected nodes **with their reasons** |
| `GET /api/agent?id=` | contribution counts, not a score |
| `GET /api/refusals?limit=` | refused writes, read from the event log |

`truncated` is reported rather than silently cutting: a truncated graph shows
fewer supporting witnesses than exist, which here changes what the picture
appears to say about support.

`/api/refusals` returns `available: false` when there's no log, rather than an
empty list — an in-memory or freshly copied projection legitimately has none,
and saying so beats implying zero refusals.

### With `--allow-writes`

| Route | Body |
|---|---|
| `POST /api/accept?id=` | — |
| `POST /api/reject?id=` | `{"reason": "..."}` |
| `POST /api/reopen?id=` | `{"reason": "..."}` |

All act as `RESEARCHER`, the one privileged identity in the ladder. Passing the
flag is the operator asserting that whoever can reach this port is the
researcher.

The `reason` is required by the **graph**, not by this layer — it's passed
through so the write boundary refuses it, keeping one rule in one place and
getting the refusal logged like any other.

Status codes carry meaning:

- **404** — no such node.
- **409** — an agent run holds the writer lock.
- **422** — the graph's own rules declined a well-formed request, returning
  `{"rule": "...", "message": "..."}`. This is *a real answer from the system*,
  not a server fault.

### With `--corpus`

| Route | Notes |
|---|---|
| `GET /api/corpus/search?q=&limit=` | exactly `source.search()` — a query typed here returns the same hits in the same order as one typed in Python. Response states `ordering: "corpus order; no relevance ranking"` |
| `GET /api/corpus/fetch?ref=&max_chars=&strip_markup=` | one record; `strip_markup` is display-only and **breaks offsets**, so never store its output |

Search returns 503 if the reader has no index, naming the reason.

### With `--allow-runs`

| Route | Notes |
|---|---|
| `GET /api/run/config` | model, ceilings, whether a corpus is present |
| `GET /api/run` | current run + history |
| `GET /api/run/{run_id}` | one run |
| `POST /api/run` | start; accepts a single agent or `agents: [...]` |
| `POST /api/run/stop` | stop after the current turn |

The browser proposes a budget; the server bounds it. A field that accepted any
number and rejected it only after the button was pressed would be worse than no
field.

Spend is shown **while the run goes**, not summarised at the end, and refusals
are shown as **results, not errors** — a run whose agent was refused five times
did not fail.

## Development

    cd cohort/ui/frontend && npm run dev     # :5173, proxies /api to :8000

The dev server and the built bundle behave identically. `npm run build` outputs
to `cohort/ui/static/`, which the API mounts when present; that directory is
gitignored and regenerated from `src/`.

Theming has **three** states, not two: an explicit choice stamps
`data-theme="light|dark"`, and "system" stamps nothing and follows
`prefers-color-scheme`. Contrast is measured against WCAG AA (4.5:1 for small
text), not eyeballed.
