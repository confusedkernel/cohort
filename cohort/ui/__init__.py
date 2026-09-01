"""The researcher UI (build order stage 5): a read-only JSON API over
`graph.py`'s existing reader surface, plus a static frontend.

Optional by construction — the core library and CLI never import from here,
and `fastapi` lives behind the `ui` extra (ROADMAP.md "Decisions already
made"). Importing this package without that extra installed fails loudly at
the import of `cohort.ui.api`, not somewhere deep in a request.
"""
