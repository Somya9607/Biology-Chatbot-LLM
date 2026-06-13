"""Qdrant collection management, upsert and ANN search.

Wraps ``qdrant-client`` with helpers to create the collection (idempotently),
upsert embedded chunks with citation payloads, and run cosine ANN search. The
collection uses an HNSW index (m=16, ef_construct=200) over 384-dim vectors.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.config import settings
from app.embeddings.embedder import EMBEDDING_DIM
from app.logger import get_logger

log = get_logger(__name__)


class QdrantUnavailableError(RuntimeError):
    """Raised when the Qdrant server cannot be reached."""


@dataclass
class SearchResult:
    """A single ANN search hit with citation metadata."""

    chunk_id: str
    text: str
    score: float
    source_file: str
    page_number: int
    chunk_index: int
    pdf_id: str
    metadata: dict = field(default_factory=dict)


def _point_id(chunk_id: str) -> str:
    """Derive a stable Qdrant point ID (UUID5) from a chunk_id string."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantManager:
    """Manage the biology_rag Qdrant collection and its operations."""

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.mode = settings.QDRANT_MODE.lower()
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection = settings.QDRANT_COLLECTION
        try:
            if self.mode == "local":
                # Embedded, on-disk Qdrant — no server/Docker required.
                self.client = QdrantClient(path=settings.QDRANT_PATH)
            else:
                self.client = QdrantClient(host=self.host, port=self.port, timeout=30.0)
        except (ResponseHandlingException, UnexpectedResponse, OSError) as exc:
            raise QdrantUnavailableError(self._unavailable_message()) from exc

    def _unavailable_message(self) -> str:
        """Return a mode-appropriate 'unavailable' error message."""
        if self.mode == "local":
            return (
                "Embedded vector database could not be opened. Ensure no other "
                f"process holds {settings.QDRANT_PATH} and that the path is writable."
            )
        return "Vector database unavailable. Start Qdrant with: docker-compose up -d qdrant"

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist (idempotent)."""
        try:
            existing = {c.name for c in self.client.get_collections().collections}
            if self.collection in existing:
                log.info("vectordb.collection_exists", collection=self.collection)
                return

            # Local (embedded) mode ignores server-side HNSW/on-disk tuning, so
            # only pass those when talking to a real server.
            extra = {}
            if self.mode != "local":
                extra = {
                    "hnsw_config": qmodels.HnswConfigDiff(m=16, ef_construct=200),
                    "on_disk_payload": True,
                }
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=EMBEDDING_DIM,
                    distance=qmodels.Distance.COSINE,
                ),
                **extra,
            )
            log.info(
                "vectordb.collection_created", collection=self.collection, mode=self.mode
            )
        except (ResponseHandlingException, UnexpectedResponse, OSError) as exc:
            raise QdrantUnavailableError(self._unavailable_message()) from exc

    def upsert_chunks(self, chunks: List, embeddings: List[np.ndarray]) -> int:
        """Upsert chunks + embeddings in batches of 100. Returns count upserted."""
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")

        points: List[qmodels.PointStruct] = []
        for chunk, vector in zip(chunks, embeddings):
            points.append(
                qmodels.PointStruct(
                    id=_point_id(chunk.chunk_id),
                    vector=vector.tolist(),
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "source_file": chunk.source_file,
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "token_count": chunk.token_count,
                        "pdf_id": chunk.metadata.get("pdf_id", ""),
                    },
                )
            )

        upserted = 0
        try:
            for start in range(0, len(points), 100):
                batch = points[start : start + 100]
                self.client.upsert(collection_name=self.collection, points=batch)
                upserted += len(batch)
        except (ResponseHandlingException, UnexpectedResponse, OSError) as exc:
            raise QdrantUnavailableError(
                "Vector database unavailable during upsert."
            ) from exc

        log.info("vectordb.upsert", count=upserted)
        return upserted

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[SearchResult]:
        """Run cosine ANN search and return up to ``top_k`` SearchResults."""
        t0 = time.perf_counter()
        try:
            # qdrant-client >= 1.10 prefers query_points(); <= 1.9 uses search().
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection,
                    query=query_vector.tolist(),
                    limit=top_k,
                    score_threshold=0.0,
                    with_payload=True,
                )
                hits = response.points
            else:
                hits = self.client.search(
                    collection_name=self.collection,
                    query_vector=query_vector.tolist(),
                    limit=top_k,
                    score_threshold=0.0,
                    with_payload=True,
                )
        except (ResponseHandlingException, UnexpectedResponse, OSError) as exc:
            raise QdrantUnavailableError(
                "Vector database unavailable during search."
            ) from exc

        results: List[SearchResult] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                SearchResult(
                    chunk_id=payload.get("chunk_id", str(hit.id)),
                    text=payload.get("text", ""),
                    score=float(hit.score),
                    source_file=payload.get("source_file", ""),
                    page_number=int(payload.get("page_number", 0)),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    pdf_id=payload.get("pdf_id", ""),
                    metadata=payload,
                )
            )

        log.info(
            "vectordb.search",
            result_count=len(results),
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        return results

    def get_collection_info(self) -> dict:
        """Return basic collection stats: points_count, name, status."""
        try:
            info = self.client.get_collection(self.collection)
            return {
                "points_count": info.points_count or 0,
                "collection_name": self.collection,
                "status": str(info.status),
            }
        except (ResponseHandlingException, UnexpectedResponse, OSError) as exc:
            log.warning("vectordb.info_failed", error=str(exc))
            return {"points_count": 0, "collection_name": self.collection, "status": "error"}

    def health_check(self) -> bool:
        """Return True if the Qdrant server responds to a collections list."""
        try:
            self.client.get_collections()
            return True
        except (ResponseHandlingException, UnexpectedResponse, OSError):
            return False
