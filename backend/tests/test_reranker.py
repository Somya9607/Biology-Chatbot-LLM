"""Tests for CrossEncoderReranker with a stubbed cross-encoder model."""
from __future__ import annotations

import pytest

from app.reranking.reranker import CrossEncoderReranker
from tests.conftest import make_search_result


class FakePredictor:
    """Scores a pair higher when the passage mentions 'cell'."""

    def predict(self, pairs):
        return [1.0 if "cell" in text.lower() else 0.1 for _q, text in pairs]


class FailingPredictor:
    def predict(self, pairs):
        raise RuntimeError("model boom")


@pytest.fixture
def reranker(monkeypatch):
    monkeypatch.setattr(CrossEncoderReranker, "_model", FakePredictor())
    return CrossEncoderReranker()


def _ten_results():
    return [make_search_result(f"passage {i}", score=0.5, page=i) for i in range(10)]


def test_rerank_reduces_results(reranker):
    out = reranker.rerank("biology", _ten_results(), top_k=4)
    assert len(out) == 4


def test_scores_are_floats(reranker):
    out = reranker.rerank("biology", _ten_results(), top_k=4)
    assert all(isinstance(r.rerank_score, float) for r in out)


def test_fallback_on_error(monkeypatch):
    monkeypatch.setattr(CrossEncoderReranker, "_model", FailingPredictor())
    reranker = CrossEncoderReranker()
    results = _ten_results()
    out = reranker.rerank("biology", results, top_k=4)
    # Graceful fallback: no crash, returns top_k ordered by vector score.
    assert len(out) == 4


def test_ranking_reflects_relevance(reranker):
    results = [
        make_search_result("photosynthesis in leaves", score=0.5, page=1),
        make_search_result("the cell membrane structure", score=0.5, page=2),
        make_search_result("ecosystem dynamics", score=0.5, page=3),
    ]
    out = reranker.rerank("biology cell", results, top_k=3)
    assert "cell" in out[0].text.lower()
