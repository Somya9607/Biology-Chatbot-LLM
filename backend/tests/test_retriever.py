"""Tests for BiologyRetriever using mock embedder + Qdrant manager."""
from __future__ import annotations

import numpy as np

from app.retrieval.retriever import BiologyRetriever
from tests.conftest import make_search_result


class FakeEmbedder:
    def embed_query(self, query: str) -> np.ndarray:
        return np.ones(384, dtype=np.float32)


class FakeQdrant:
    def __init__(self, results):
        self._results = results

    def search(self, query_vector, top_k=10):
        return list(self._results[:top_k])


def test_retrieve_returns_top_k():
    results = [make_search_result(f"chunk {i}", score=1.0 - i * 0.1, page=i) for i in range(10)]
    retriever = BiologyRetriever(FakeEmbedder(), FakeQdrant(results))
    out = retriever.retrieve("cells", top_k=4)
    assert len(out) == 4


def test_results_sorted_by_score():
    results = [
        make_search_result("low", score=0.2, page=1),
        make_search_result("high", score=0.9, page=2),
        make_search_result("mid", score=0.5, page=3),
    ]
    retriever = BiologyRetriever(FakeEmbedder(), FakeQdrant(results))
    out = retriever.retrieve("cells", top_k=3)
    scores = [r.score for r in out]
    assert scores == sorted(scores, reverse=True)


def test_empty_db_returns_empty_list():
    retriever = BiologyRetriever(FakeEmbedder(), FakeQdrant([]))
    assert retriever.retrieve("cells", top_k=5) == []
