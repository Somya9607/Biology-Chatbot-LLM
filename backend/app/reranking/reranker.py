"""Cross-encoder reranking of retrieved candidates.

Uses ``cross-encoder/ms-marco-MiniLM-L-6-v2`` to jointly score (query, passage)
pairs, which is more accurate than bi-encoder cosine similarity for final
ordering. The model is cached on the class. On any failure the reranker
degrades gracefully and returns the input results ordered by vector score.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from app.config import settings
from app.logger import get_logger
from app.vectordb.qdrant_client import SearchResult

if TYPE_CHECKING:  # heavy import only for type checkers, not at runtime
    from sentence_transformers import CrossEncoder

log = get_logger(__name__)


@dataclass
class RankedResult(SearchResult):
    """A SearchResult enriched with cross-encoder rerank information."""

    rerank_score: float = 0.0
    original_rank: int = 0
    final_rank: int = 0


class CrossEncoderReranker:
    """Rerank retrieved candidates with a cached cross-encoder model."""

    _model: "CrossEncoder | None" = None

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.RERANKER_MODEL
        self._load_model()

    def _load_model(self) -> None:
        """Load the CrossEncoder model once and cache it on the class."""
        if CrossEncoderReranker._model is None:
            from sentence_transformers import CrossEncoder

            log.info("reranking.model_loading", model=self.model_name)
            CrossEncoderReranker._model = CrossEncoder(self.model_name)
            log.info("reranking.model_loaded", model=self.model_name)

    @property
    def model(self) -> "CrossEncoder":
        """Return the cached cross-encoder model, loading if necessary."""
        if CrossEncoderReranker._model is None:
            self._load_model()
        assert CrossEncoderReranker._model is not None
        return CrossEncoderReranker._model

    def rerank(
        self, query: str, results: List[SearchResult], top_k: int | None = None
    ) -> List[RankedResult]:
        """Rerank ``results`` for ``query`` and return the top ``top_k``.

        On model failure, returns the input ordered by vector score as
        RankedResults (graceful fallback), never raising.
        """
        k = top_k or settings.TOP_K_RERANK
        if not results:
            return []

        t0 = time.perf_counter()
        try:
            pairs = [(query, r.text) for r in results]
            scores = self.model.predict(pairs)
            order = sorted(
                range(len(results)),
                key=lambda i: float(scores[i]),
                reverse=True,
            )
            ranked = self._build_ranked(results, order, scores)
        except (RuntimeError, ValueError) as exc:
            log.error("reranking.failed_fallback", error=str(exc))
            ranked = self._fallback(results)

        output = ranked[:k]
        log.info(
            "reranking.complete",
            input_count=len(results),
            output_count=len(output),
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        return output

    @staticmethod
    def _build_ranked(
        results: List[SearchResult], order: List[int], scores
    ) -> List[RankedResult]:
        """Assemble RankedResults from a sort order and cross-encoder scores."""
        ranked: List[RankedResult] = []
        for final_rank, idx in enumerate(order):
            r = results[idx]
            ranked.append(
                RankedResult(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    score=r.score,
                    source_file=r.source_file,
                    page_number=r.page_number,
                    chunk_index=r.chunk_index,
                    pdf_id=r.pdf_id,
                    metadata=r.metadata,
                    rerank_score=float(scores[idx]),
                    original_rank=idx,
                    final_rank=final_rank,
                )
            )
        return ranked

    @staticmethod
    def _fallback(results: List[SearchResult]) -> List[RankedResult]:
        """Return results ordered by vector score when reranking fails."""
        ordered = sorted(results, key=lambda r: r.score, reverse=True)
        return [
            RankedResult(
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                source_file=r.source_file,
                page_number=r.page_number,
                chunk_index=r.chunk_index,
                pdf_id=r.pdf_id,
                metadata=r.metadata,
                rerank_score=r.score,
                original_rank=i,
                final_rank=i,
            )
            for i, r in enumerate(ordered)
        ]
