"""cbeta_markup: the two TEI parsers stage 4 depends on.

The `<cb:docNumber>` strings below are real syntax observed in CBETA v061,
reproduced here because they are *markup*, not corpus text — no scripture
content is copied into this repository (HANDOFF.md's corpus-bytes rule).
"""
from __future__ import annotations

from cohort.sources.cbeta_markup import (
    edition_families,
    parse_apparatus,
    parse_parallel_refs,
)


def _doc(docnumber: str) -> str:
    return f"<TEI><text><cb:docNumber>{docnumber}</cb:docNumber></text></TEI>"


def _numbers(refs) -> list[str]:
    return [r.number for r in refs]


# --- parallel cross-references ------------------------------------------------

def test_bare_list_is_asserted():
    r = parse_parallel_refs(_doc("No. 516 [Nos. 514, 515]"))
    assert r.self_number == "516"
    assert _numbers(r.asserted) == ["514", "515"]
    assert r.compare_only == []


def test_cf_list_is_never_asserted():
    r = parse_parallel_refs(_doc("No. 1754 [cf. No. 365]"))
    assert r.asserted == []
    assert _numbers(r.compare_only) == ["365"]


def test_cf_and_asserted_split_by_position_within_one_bracket():
    """The corpus mixes both in a single bracket; `cf.` must not poison the
    references that precede it, nor the ones after it be promoted."""
    r = parse_parallel_refs(_doc("No. 1597 [Nos. 1595, 1596; cf. Nos. 1592-1594, 1598]"))
    assert _numbers(r.asserted) == ["1595", "1596"]
    assert _numbers(r.compare_only) == ["1592", "1593", "1594", "1598"]


def test_ranges_expand_and_keep_document_order():
    r = parse_parallel_refs(_doc("No. 251 [Nos. 250, 252-255, 257]"))
    assert _numbers(r.asserted) == ["250", "252", "253", "254", "255", "257"]


def test_sub_references_are_captured_but_not_part_of_the_number():
    r = parse_parallel_refs(_doc("No. 285 [Nos. 278(22), 279(26), 286, 287]"))
    assert _numbers(r.asserted) == ["278", "279", "286", "287"]
    assert [r.sub_ref for r in r.asserted] == ["22", "26", None, None]


def test_part_of_is_kept_separate_from_parallelism():
    r = parse_parallel_refs(_doc("No. 294 [Part of No. 278(34), 279(39), 293]"))
    assert r.asserted == []
    assert _numbers(r.part_of) == ["278", "279", "293"]


def test_lettered_taisho_numbers_survive():
    r = parse_parallel_refs(_doc("No. 1887B [cf. No. 1887A]"))
    assert r.self_number == "1887B"
    assert _numbers(r.compare_only) == ["1887A"]


def test_embedded_tags_inside_a_bracket_are_stripped():
    r = parse_parallel_refs(
        _doc('No. 123 [No. 99(1248), <lb n="0546a12" ed="T"/> No. 124]')
    )
    assert _numbers(r.asserted) == ["99", "124"]


def test_trailing_chinese_title_does_not_discard_good_numbers():
    """The corpus annotates some lists with a Chinese title after a
    semicolon. That prose must not poison the references beside it."""
    r = parse_parallel_refs(_doc("No. 449 [Nos. 450, 451; 灌頂經卷第十二]"))
    assert _numbers(r.asserted) == ["450", "451"]
    assert r.unparsed == []


def test_digit_bearing_segment_after_a_semicolon_must_still_parse():
    """Only digit-free annotations are droppable. A segment carrying digits
    is a reference list and has to parse cleanly or the bracket is refused."""
    r = parse_parallel_refs(
        _doc("No. 293 [Fasc. 1-39 = Nos. 278(34), 279 (39); Fasc. 40 = Nos. 296, 297]")
    )
    assert r.asserted == []
    assert len(r.unparsed) == 1


def test_non_taisho_bracket_is_reported_unparsed_not_half_read():
    """A Pali/Sanskrit cross-reference is not a Taisho list. Reading the
    stray digits out of it would mint false parallels."""
    r = parse_parallel_refs(_doc("No. 96 [~M. 118【CB】，5【大】85, Ānāpānasati sutta.]"))
    assert r.asserted == []
    assert r.compare_only == []
    assert len(r.unparsed) == 1
    assert "Ānāpānasati" in r.unparsed[0]


def test_repeated_reference_across_two_brackets_is_deduped():
    r = parse_parallel_refs(_doc("No. 270［－］【CB】，[No. 271]【大】 [No. 271]"))
    assert _numbers(r.asserted) == ["271"]


def test_document_without_brackets_yields_empty_buckets():
    r = parse_parallel_refs(_doc("No. 1234"))
    assert r.self_number == "1234"
    assert (r.asserted, r.compare_only, r.part_of, r.unparsed) == ([], [], [], [])


# --- apparatus ---------------------------------------------------------------

APP_DOC = (
    "<TEI><text>"
    '<app n="0848003"><lem wit="【大】">A</lem>'
    '<rdg wit="【宋】 【元】 【明】" resp="Taisho">B</rdg></app>'
    '<app n="0311b0201"><lem wit="【CB】" resp="CBETA.maha">C</lem>'
    '<rdg wit="【金藏】">D</rdg></app>'
    "</text></TEI>"
)


def test_apparatus_parses_lemma_and_variants():
    entries = parse_apparatus(APP_DOC)
    assert len(entries) == 2
    first = entries[0]
    assert first.n == "0848003"
    assert first.lemma.sigla == ["【大】"]
    assert first.lemma.text == "A"
    assert len(first.variants) == 1
    assert first.variants[0].resp == "Taisho"


def test_joint_sigla_stay_one_group():
    """Splitting `【宋】 【元】 【明】` into three would turn one
    shared-descent family into three independent confirmations."""
    entries = parse_apparatus(APP_DOC)
    assert entries[0].variants[0].sigla == ["【宋】", "【元】", "【明】"]


def test_edition_families_keys_on_the_group_as_written():
    tally = edition_families(parse_apparatus(APP_DOC))
    assert tally["【宋】 【元】 【明】"] == 1
    assert tally["【大】"] == 1
    assert "【宋】" not in tally  # never split out on its own


def test_editorial_emendation_is_visible_via_resp():
    entries = parse_apparatus(APP_DOC)
    assert entries[1].lemma.resp == "CBETA.maha"
    assert entries[1].lemma.sigla == ["【CB】"]


def test_document_without_apparatus_yields_nothing():
    assert parse_apparatus("<TEI><text>plain</text></TEI>") == []
