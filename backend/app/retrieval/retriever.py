"""Dense retrieval: embed a query and run ANN search over Qdrant.

Composes :class:`BiologyEmbedder` and :class:`QdrantManager`. Results are
returned sorted by vector similarity (descending). The shared
:class:`SearchResult` dataclass lives in the vectordb module.
"""
from __future__ import annotations

import time
from typing import List

from app.config import settings
from app.embeddings.embedder import BiologyEmbedder
from app.logger import get_logger
from app.vectordb.qdrant_client import QdrantManager, SearchResult

log = get_logger(__name__)


class BiologyRetriever:
    """Retrieve top-K candidate chunks for a query via dense ANN search."""

    def __init__(self, embedder: BiologyEmbedder, qdrant_manager: QdrantManager) -> None:
        self.embedder = embedder
        self.qdrant_manager = qdrant_manager

    def retrieve(self, query: str, top_k: int | None = None) -> List[SearchResult]:
        """Embed ``query`` and return up to ``top_k`` results, score-descending.

        Args:
            query: User question text.
            top_k: Number of candidates to fetch (defaults to settings).

        Returns:
            SearchResults sorted by vector score descending.
        """
        k = top_k or settings.TOP_K_RETRIEVAL
        t0 = time.perf_counter()

        query_vector = self.embedder.embed_query(query)
        results = self.qdrant_manager.search(query_vector, top_k=k)
        results.sort(key=lambda r: r.score, reverse=True)

        log.info(
            "retrieval.complete",
            query_preview=query[:50],
            result_count=len(results),
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        return results
