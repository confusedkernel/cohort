# Command-line reference

Every runnable entry point, what it needs, and what it costs.

**The rule that governs this whole directory: anything that calls a model is
manual-only and is never run by the test suite.** Each such script names its own
cost in its docstring, and spend is capped in code
([agents.md](agents.md)), not estimated.

## No corpus, no key, no network

| Command | What it does |
|---|---|
| `.venv/bin/pytest -q` | 260 tests |
| `.venv/bin/python demo.py` | the `independent_support()` flip — **show this first** |

`demo.py` prints the thing worth seeing before anything else: a claim whose
support count stays at two while its independence flag goes false the moment a
`parallel_of` edge is recorded. That is the counter-argument to
consensus-seeking, in three lines of output. It also prints its own refusal log,
because refusals are output.

## Corpus, no model call

These need `CBETA_ARCHIVE_PATH`. None of them spends money.

| Command | Cost | Notes |
|---|---|---|
| `scripts/build_cbeta_index.py` | ~432s, 1.14 GB | one-off full-corpus FTS index. `--db`, `--prefix`, `--limit`, `--sha256` |
| `scripts/search_cbeta.py 色即是空` | ~65ms | needs the index. `--limit`, `--collection`, `--fetch`, `--db` |
| `scripts/scan_parallels.py` | ~8s, read-only | validates the `<cb:docNumber>` parser over all 20,190 entries. `--out`, `--limit` |
| `scripts/run_stage4_demo.py` | free | stage 4 on real text: shared descent recognised, consensus refused |
| `scripts/seed_demo_graph.py` | free | builds the demo graph for the UI from the **real** archive. `--db`, `--force` |

`scripts/search_cbeta.py` is a thin front end on the same `CbetaReader.search()`
the tools use, so what a researcher sees here is exactly what an agent gets.
`--fetch` proves every hit is fetchable, at the cost of a full archive
re-verification per hit.

`scripts/run_stage4_demo.py` is the sharpest demonstration in the repo and needs
no API key: T08n0250, T08n0251 and T08n0252 are three *different* Chinese
translations that all contain 色即是空，空即是色. A fact-checking model counts
that as three independent confirmations. It isn't — CBETA's own
`<cb:docNumber>` lists them as parallel texts. The script shows COHORT reaching
that conclusion **from the corpus's own markup**, not from a hand-added edge as
`demo.py` necessarily does.

`scripts/scan_parallels.py` writes three artifacts to `~/cbeta_scan/`:
`parallel_map.jsonl`, `unparsed.txt` (every bracket the parser declined, deduped
with an example each — i.e. its own failure report), and `summary.txt`.

## Live model calls — manual only

Need `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`. **Never paste a real key into
a chat session.**

| Command | Cost | Notes |
|---|---|---|
| `scripts/smoke_openrouter.py` | ~$0.0002 | one real call; run once against a new key before trusting it |
| `scripts/run_cbeta_demo.py` | ~$0.002 | one agent against the real archive |
| `scripts/run_swarm_demo.py` | ~$0.003 | two *concurrent* real agents, distinct declared scope |
| `scripts/run_conjecture_demo.py` | ~$0.004 | the falsifiability gate live. `--budget` (default $0.25), `--max-turns` (4), `--db` |

## The UI

    .venv/bin/python scripts/serve_ui.py --db demo_graph.sqlite

| Flag | Default | Effect |
|---|---|---|
| `--db` | `demo_graph.sqlite` | the projection to serve |
| `--log` | `--db` with `.jsonl` | event log, for the refusal panel |
| `--host` / `--port` | `127.0.0.1` / `8000` | binds locally **deliberately** — the corpus is licence-restricted |
| `--corpus` | off | corpus browse/search |
| `--allow-writes` | off | accept/reject/reopen, acting as `RESEARCHER` |
| `--allow-runs` | off | the agent-run launcher (implies `--corpus`) — **spends money** |
| `--max-budget` | 1.00 | hard per-run ceiling the browser cannot raise |
| `--reload` | off | dev autoreload |

See [ui.md](ui.md) for the HTTP surface and for port forwarding over SSH.

## Environment variables

    OPENROUTER_API_KEY=      # live scripts and UI runs
    OPENROUTER_MODEL=
    CBETA_ARCHIVE_PATH=      # anything touching the real corpus
    CBETA_FTS_PATH=          # optional; defaults to cbeta_fts.sqlite

Copy `.env.example` to `.env` and fill it in by hand. `.env` is gitignored.
