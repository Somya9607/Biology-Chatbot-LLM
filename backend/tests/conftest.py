"""Shared pytest fixtures and lightweight stubs.

Heavy components (real embedding/reranker models, Qdrant server, Ollama) are
replaced with deterministic stubs so the suite runs offline and fast. Tests
that genuinely require a real model are guarded with skips.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure the backend package root is importable when running `pytest tests/`.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Keep transient files (logs, fingerprints) inside a temp area during tests.
os.environ.setdefault("LOG_DIR", str(BACKEND_ROOT / "logs"))


@pytest.fixture
def tmp_fingerprint_file(tmp_path) -> str:
    """Return a path to an isolated fingerprint registry file."""
    return str(tmp_path / "indexed_docs.json")


def make_page(page_number: int, text: str, is_scanned: bool = False):
    """Build a PageContent without importing fitz at collection time."""
    from app.ingestion.extractor import PageContent

    return PageContent(
        page_number=page_number,
        text=text,
        is_scanned=is_scanned,
        source_file="sample.pdf",
        bounding_boxes=None,
    )


def make_search_result(text: str, score: float, page: int = 1, source: str = "bio.pdf"):
    """Build a SearchResult for retriever/reranker tests."""
    from app.vectordb.qdrant_client import SearchResult

    return SearchResult(
        chunk_id=f"c{page}-{score}",
        text=text,
        score=score,
        source_file=source,
        page_number=page,
        chunk_index=page,
        pdf_id="md5abc",
        metadata={},
    )
