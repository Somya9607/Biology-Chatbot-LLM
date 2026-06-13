"""Dense embedding generation with BAAI/bge-small-en-v1.5 (384-dim).

The model is loaded lazily and cached as a class attribute so it is only
instantiated once per process (shared across requests). BGE retrieval models
require a query-side instruction prefix; document chunks are embedded as-is.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, List

import numpy as np

from app.config import settings
from app.logger import get_logger

if TYPE_CHECKING:  # heavy import only for type checkers, not at runtime
    from sentence_transformers import SentenceTransformer

log = get_logger(__name__)

# BGE models expect this instruction prefix on the query side only.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
EMBEDDING_DIM = 384
BATCH_SIZE = 64


class BiologyEmbedder:
    """Sentence-Transformers BGE embedder with a process-wide model cache."""

    _model: "SentenceTransformer | None" = None

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._load_model()

    def _load_model(self) -> None:
        """Load the SentenceTransformer model once and cache it on the class."""
        if BiologyEmbedder._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("embedding.model_loading", model=self.model_name)
            BiologyEmbedder._model = SentenceTransformer(self.model_name)
            log.info("embedding.model_loaded", model=self.model_name, dim=EMBEDDING_DIM)

    @property
    def model(self) -> "SentenceTransformer":
        """Return the cached model, loading it if necessary."""
        if BiologyEmbedder._model is None:
            self._load_model()
        assert BiologyEmbedder._model is not None
        return BiologyEmbedder._model

    def embed_chunks(self, chunks: List) -> List[np.ndarray]:
        """Embed a list of ChunkData (or strings) into float32 vectors.

        Processed in batches of 64. Returns one 384-dim float32 array per item.
        """
        if not chunks:
            return []

        texts = [c.text if hasattr(c, "text") else str(c) for c in chunks]
        vectors: List[np.ndarray] = []

        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            t0 = time.perf_counter()
            arr = self.model.encode(
                batch,
                batch_size=BATCH_SIZE,
                normalize_embeddings=True,
                show_progress_bar=True,
                convert_to_numpy=True,
            ).astype(np.float32)
            vectors.extend(arr[i] for i in range(arr.shape[0]))
            log.info(
                "embedding.batch_complete",
                batch_size=len(batch),
                elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
            )

        return vectors

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string (with the BGE query prefix)."""
        prefixed = f"{BGE_QUERY_PREFIX}{query}"
        vector = self.model.encode(
            prefixed,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)
        return vector
