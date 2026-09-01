"""LocalReader: manifest discipline and the FTS5 character-unigram search
(design doc §13 carry-over: nothing inferred from a filename)."""
from __future__ import annotations

from pathlib import Path

import pytest

from cohort.sources.local_reader import LocalReader, ManifestError

FIXTURE = Path(__file__).parent.parent / "examples" / "local_corpus"


@pytest.fixture
def reader():
    r = LocalReader(FIXTURE)
    yield r
    r.close()


def test_search_finds_a_known_substring(reader):
    hits = reader.search("明月")
    refs = {h.ref for h in hits}
    assert "texts/libai-jingyesi.txt" in refs


def test_search_respects_max_results(reader):
    # "人" appears in both 鹿柴 ("不見人"/"但聞人語") and 江雪 ("人蹤滅")
    hits = reader.search("人", max_results=1)
    assert len(hits) == 1


def test_search_for_absent_text_returns_nothing(reader):
    assert reader.search("這個語料庫裡沒有這句話") == []


def test_fetch_returns_full_text_and_witness_ref(reader):
    hits = reader.search("空山")
    record = reader.fetch(hits[0].ref)
    assert record.witness_ref == "poem:wangwei-luchai"
    assert "空山不見人" in record.text


def test_fetch_unknown_ref_raises(reader):
    with pytest.raises(KeyError):
        reader.fetch("texts/does-not-exist.txt")


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(ManifestError, match="no manifest"):
        LocalReader(tmp_path)


def test_manifest_missing_required_column_raises(tmp_path):
    (tmp_path / "manifest.csv").write_text("path,label\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="witness_ref"):
        LocalReader(tmp_path)


def test_manifest_path_escaping_root_raises(tmp_path):
    (tmp_path / "manifest.csv").write_text(
        "path,witness_ref\n../outside.txt,w:1\n", encoding="utf-8"
    )
    with pytest.raises(ManifestError, match="escapes"):
        LocalReader(tmp_path)


def test_stats_report_unlisted_files(tmp_path):
    (tmp_path / "manifest.csv").write_text(
        "path,witness_ref\ntexts/a.txt,w:a\n", encoding="utf-8"
    )
    (tmp_path / "texts").mkdir()
    (tmp_path / "texts" / "a.txt").write_text("甲文", encoding="utf-8")
    (tmp_path / "texts" / "b.txt").write_text("乙文", encoding="utf-8")
    r = LocalReader(tmp_path)
    try:
        assert r.stats["records"] == 1
        assert r.stats["unlisted_files"] == 1
        assert "texts/b.txt" in r.stats["unlisted_examples"]
    finally:
        r.close()
