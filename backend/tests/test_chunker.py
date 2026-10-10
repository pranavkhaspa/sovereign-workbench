from __future__ import annotations

from sovereign_workbench.core.rag.chunker import chunk_pages


def test_chunks_split_with_overlap():
    pages = [(1, "word " * 400)]
    chunks = chunk_pages(pages, size=200, overlap=40)
    assert len(chunks) > 1
    assert all(chunk.page == 1 for chunk in chunks)


def test_empty_page_is_skipped():
    assert chunk_pages([(1, "   "), (2, "")]) == []


def test_overlap_must_be_smaller_than_size():
    import pytest

    with pytest.raises(ValueError):
        chunk_pages([(1, "abc")], size=10, overlap=10)
