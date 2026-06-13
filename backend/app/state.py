"""Shared application component container.

Heavy components (embedder, reranker, Qdrant, retriever, generator) are loaded
once at FastAPI startup and stored here so route handlers can reach them
without re-instantiating per request. Population happens in ``main.py``.
"""
from __future__ import annotations

from typing import Optional

from app.embeddings.embedder import BiologyEmbedder
from app.generation.generator import OllamaGenerator
from app.ingestion.chunker import TextChunker
from app.ingestion.cleaner import TextCleaner
from app.ingestion.extractor import PDFExtractor
from app.ingestion.fingerprint import DocumentFingerprintManager
from app.ingestion.ocr import OCRProcessor
from app.reranking.reranker import CrossEncoderReranker
from app.retrieval.retriever import BiologyRetriever
from app.vectordb.qdrant_client import QdrantManager


class AppState:
    """Holds singletons for the lifetime of the process."""

    embedder: Optional[BiologyEmbedder] = None
    reranker: Optional[CrossEncoderReranker] = None
    qdrant: Optional[QdrantManager] = None
    retriever: Optional[BiologyRetriever] = None
    generator: Optional[OllamaGenerator] = None

    # Ingestion components (lightweight, but shared for consistency).
    extractor: Optional[PDFExtractor] = None
    ocr: Optional[OCRProcessor] = None
    cleaner: Optional[TextCleaner] = None
    chunker: Optional[TextChunker] = None
    fingerprints: Optional[DocumentFingerprintManager] = None


app_state = AppState()
"""Module-level singleton container."""
