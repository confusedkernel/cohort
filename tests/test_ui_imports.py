"""Every API helper a panel calls must be imported by that panel.

A free identifier is not a build error — Vite bundles `getQuestions(...)` with
nothing named `getQuestions` in scope perfectly happily, and the failure
arrives as a blank tab and a ReferenceError in a console nobody was watching.
That is how the Inquiry panel shipped broken on 2026-09-02: an import patch
matched nothing, `npm run build` passed, the Python suite passed, and the tab
threw on first render.

So the cheap half of what a JS test runner would give us, without adding one:
resolve the calls statically. It cannot catch a wrong argument or a bad render,
but it catches the whole class of "the name is not there".
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "cohort" / "ui" / "frontend" / "src"

pytestmark = pytest.mark.skipif(
    not (SRC / "api.js").is_file(), reason="frontend sources not present"
)


def _api_exports() -> set[str]:
    src = (SRC / "api.js").read_text(encoding="utf-8")
    return set(re.findall(r"^export (?:const|function|async function)\s+(\w+)", src, re.M))


def _imported(src: str) -> set[str]:
    """Names this module brings in, from any `import { ... } from`, on one line
    or several."""
    names: set[str] = set()
    for block in re.findall(r"import\s*\{([^}]*)\}\s*from", src, re.S):
        for part in block.split(","):
            part = part.strip()
            if part:
                names.add(part.split(" as ")[-1].strip())
    return names


def _local_defs(src: str) -> set[str]:
    return set(
        re.findall(r"^(?:export\s+)?(?:default\s+)?function\s+(\w+)", src, re.M)
    ) | set(re.findall(r"^\s*(?:const|let|var)\s+(\w+)\s*=", src, re.M))


@pytest.mark.parametrize(
    "path", sorted(SRC.glob("*.jsx")), ids=lambda p: p.name,
)
def test_every_api_call_is_in_scope(path):
    src = path.read_text(encoding="utf-8")
    exports = _api_exports()
    available = _imported(src) | _local_defs(src)
    called = {
        name for name in re.findall(r"\b(\w+)\s*\(", src) if name in exports
    }
    missing = sorted(called - available)
    assert not missing, (
        f"{path.name} calls {missing} from api.js without importing them — "
        "this builds cleanly and throws on first render"
    )


def test_the_guard_would_have_caught_the_inquiry_regression(tmp_path):
    """The test above only works if `_imported` reads a single-line import,
    which is the specific thing that went wrong: the patch that added the names
    assumed a multi-line import list and matched nothing."""
    one_line = "import { getRuns, startRun } from './api'"
    multi = "import {\n  getRuns,\n  startRun,\n} from './api'"
    assert _imported(one_line) == {"getRuns", "startRun"}
    assert _imported(multi) == {"getRuns", "startRun"}
