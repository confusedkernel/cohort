"""Guards on the frontend stylesheet that a human cannot check by reading it.

These are cheap text assertions, not a rendering test — but they cover the two
mistakes this sheet is actually prone to, both of which are invisible until
someone switches theme:

1. The light palette is written **twice** — once under
   `@media (prefers-color-scheme: light)` for "system", once under
   `:root[data-theme="light"]` for an explicit choice. CSS cannot share a
   declaration list between a media query and a plain selector, and adding a
   preprocessor would be a build step this project does not otherwise need. So
   the duplication is deliberate, and this test is what keeps the two copies
   honest.

2. A hardcoded `rgba(255,255,255,…)` surface reads as white-on-white the moment
   the theme flips. Every overlay must go through the `--fill-*` ladder or a
   named surface token.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS_PATH = (
    Path(__file__).parent.parent / "cohort" / "ui" / "frontend" / "src" / "styles.css"
)

pytestmark = pytest.mark.skipif(
    not CSS_PATH.is_file(), reason="frontend sources not present"
)


@pytest.fixture(scope="module")
def css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def _tokens(block: str) -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in re.findall(r"(--[\w-]+):\s*([^;]+);", block)
    }


def _root_block(css: str) -> str:
    m = re.search(r"\n:root \{(.*?)\n\}", css, re.S)
    assert m, "no bare :root block"
    return m.group(1)


def _light_media_block(css: str) -> str:
    m = re.search(
        r'@media \(prefers-color-scheme: light\) \{\s*'
        r':root:not\(\[data-theme="dark"\]\) \{(.*?)\n  \}\n\}',
        css, re.S,
    )
    assert m, "no prefers-color-scheme: light block"
    return m.group(1)


def _light_attr_block(css: str) -> str:
    m = re.search(r':root\[data-theme="light"\] \{(.*?)\n\}', css, re.S)
    assert m, "no :root[data-theme=light] block"
    return m.group(1)


def test_the_two_light_palettes_have_not_drifted(css):
    """The system-light and explicitly-light palettes must be identical. If
    they diverge, one of the two theme paths quietly gets different colours."""
    from_media = _tokens(_light_media_block(css))
    from_attr = _tokens(_light_attr_block(css))
    assert from_media, "light media block defines no tokens"
    assert from_media == from_attr, (
        "the two light palettes have drifted:\n"
        f"  only in media query: {sorted(set(from_media) - set(from_attr))}\n"
        f"  only in [data-theme]: {sorted(set(from_attr) - set(from_media))}\n"
        "  differing values: "
        + str({
            k: (from_media[k], from_attr[k])
            for k in set(from_media) & set(from_attr)
            if from_media[k] != from_attr[k]
        })
    )


def test_every_light_token_has_a_dark_default(css):
    """Dark is the base on `:root`. A token defined only in a light block would
    be undefined whenever the theme is dark, and `var()` with no fallback
    resolves to nothing — a silently missing colour."""
    dark = _tokens(_root_block(css))
    light = _tokens(_light_attr_block(css))
    missing = sorted(set(light) - set(dark))
    assert not missing, f"defined for light but not for dark: {missing}"


def test_no_hardcoded_white_overlays_outside_the_palette(css):
    """Overlays must come from the `--fill-*` ladder so they invert with the
    theme. Inside the token blocks they are the definitions themselves; in the
    body of the sheet they are a light-mode bug."""
    _, sep, body = css.partition("* { box-sizing: border-box; }")
    assert sep, "could not locate the end of the token blocks"
    offenders = re.findall(r"[^\n;{]*rgba\(\s*255,\s*255,\s*255[^\n;]*", body)
    assert not offenders, "hardcoded white overlays in the sheet body:\n" + "\n".join(
        o.strip() for o in offenders[:10]
    )


def test_theme_is_switchable_in_all_three_states(css):
    """`system` stamps no attribute; light and dark each need a selector that
    beats the media query, or an explicit choice would lose to the OS."""
    assert 'prefers-color-scheme: light' in css
    assert ':root[data-theme="light"]' in css
    assert ':root:not([data-theme="dark"])' in css, (
        "the media query must exclude an explicit dark choice, or picking dark "
        "on a light-preferring OS would be overridden"
    )


def test_discounting_edges_stay_distinguishable_without_hue(css):
    """DESIGN.md §10: a restyle must not reduce `parallel_of`/`descends_from`
    to a colour difference. They carry the argument that agreement between
    related witnesses is not independent confirmation, so they must also differ
    in dash pattern and weight — which survives a theme switch and colour
    blindness alike."""
    # anchored to line start so this matches the SVG rule, not `.swatch.e-discount`
    m = re.search(r"^\.e-discount \{([^}]*)\}", css, re.M)
    assert m, "no .e-discount rule for graph edges"
    rule = m.group(1)
    assert "stroke-dasharray" in rule, "discounting edges lost their dash pattern"
    assert "stroke-width" in rule, "discounting edges lost their distinct weight"

    contradicts = re.search(r"^\.e-contradicts \{([^}]*)\}", css, re.M)
    assert contradicts and "stroke-width" in contradicts.group(1), (
        "contradiction must stay as heavy as agreement (DESIGN.md §10)"
    )

    # the legend has to teach the same distinction, or the graph is a code the
    # reader has not been given
    swatch = re.search(r"\.swatch\.e-discount \{([^}]*)\}", css)
    assert swatch and "dashed" in swatch.group(1), (
        "the legend swatch for discounting edges must be dashed too"
    )
