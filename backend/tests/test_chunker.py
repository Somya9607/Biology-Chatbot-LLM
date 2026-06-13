"""Tests for TextChunker token bounds, overlap and metadata."""
from __future__ import annotations

from app.ingestion.chunker import TextChunker
from tests.conftest import make_page


def _long_text(sentences: int = 400) -> str:
    return " ".join(
        f"Cell biology fact number {i} about organelles and membranes."
        for i in range(sentences)
    )


def test_chunks_within_size_limit():
    chunker = TextChunker(chunk_size=750, chunk_overlap=150)
    pages = [make_page(1, _long_text())]
    chunks = chunker.chunk_pages(pages, "sample.pdf", "md5abc")
    assert chunks
    assert all(c.token_count <= 750 for c in chunks)


def test_overlap_exists():
    chunker = TextChunker(chunk_size=200, chunk_overlap=60)
    pages = [make_page(1, _long_text(300))]
    chunks = chunker.chunk_pages(pages, "sample.pdf", "md5abc")
    assert len(chunks) >= 2
    # Adjacent chunks should share at least one token of text.
    a_words = set(chunks[0].text.split())
    b_words = set(chunks[1].text.split())
    assert len(a_words & b_words) > 0


def test_metadata_populated():
    chunker = TextChunker()
    chunks = chunker.chunk_pages([make_page(7, _long_text(50))], "sample.pdf", "md5abc")
    for c in chunks:
        assert c.source_file == "sample.pdf"
        assert c.page_number == 7
        assert c.chunk_id
        assert c.metadata["pdf_id"] == "md5abc"


def test_empty_text_returns_empty_list():
    chunker = TextChunker()
    assert chunker.chunk_pages([make_page(1, "")], "sample.pdf", "md5abc") == []


def test_short_text_single_chunk():
    chunker = TextChunker(chunk_size=750, chunk_overlap=150)
    chunks = chunker.chunk_pages(
        [make_page(1, "Mitochondria produce ATP.")], "sample.pdf", "md5abc"
    )
    assert len(chunks) == 1
