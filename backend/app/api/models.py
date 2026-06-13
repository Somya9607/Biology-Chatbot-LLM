"""Pydantic request/response models for the API layer."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# --- Chat ------------------------------------------------------------------
class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    query: str = Field(..., min_length=1, max_length=500, description="User question")
    top_k: int = Field(default=10, ge=1, le=50, description="Retrieval candidates")
    top_k_rerank: int = Field(default=4, ge=1, le=20, description="Results after reranking")


class CitationModel(BaseModel):
    """A source citation: filename + page number."""

    source_file: str
    page_number: int


class RetrievedChunkModel(BaseModel):
    """One retrieved + reranked chunk, surfaced for explainability."""

    text: str
    source_file: str
    page_number: int
    vector_score: float
    rerank_score: float
    rank: int


class LatencyModel(BaseModel):
    """Per-stage and total latency in milliseconds."""

    retrieval_ms: float
    reranking_ms: float
    generation_ms: float
    total_ms: float


class ChatResponse(BaseModel):
    """Response body for POST /chat."""

    answer: str
    citations: List[CitationModel]
    retrieved_chunks: List[RetrievedChunkModel]
    latency: LatencyModel
    model_used: str


# --- Ingest ----------------------------------------------------------------
class IngestDirRequest(BaseModel):
    """JSON body for ingesting a server-side directory of PDFs."""

    pdf_dir: Optional[str] = Field(default=None, description="Server-side PDF directory")


class IngestFileResult(BaseModel):
    """Per-file ingestion outcome."""

    filename: str
    status: str  # "indexed" | "skipped" | "error"
    chunks_created: int
    message: str


class IngestResponse(BaseModel):
    """Response body for POST /ingest."""

    results: List[IngestFileResult]
    total_indexed: int
    total_skipped: int
    total_errors: int
    elapsed_seconds: float


class IngestStatusResponse(BaseModel):
    """Response body for POST /ingest/status."""

    indexed_documents: List[dict]
    total_chunks_in_db: int
