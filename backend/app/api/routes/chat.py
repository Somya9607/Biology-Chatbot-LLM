"""Chat endpoint: retrieve -> rerank -> generate, with full latency tracking."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from app.api.models import (
    ChatRequest,
    ChatResponse,
    CitationModel,
    LatencyModel,
    RetrievedChunkModel,
)
from app.config import settings
from app.generation.generator import OllamaModelNotFoundError, OllamaUnavailableError
from app.logger import get_logger
from app.monitoring.metrics import metrics_tracker
from app.state import app_state
from app.vectordb.qdrant_client import QdrantUnavailableError

log = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Run the RAG pipeline for a single user query.

    Stages: dense retrieval -> cross-encoder reranking -> LLM generation.
    Returns the grounded answer, citations, the reranked chunks (for
    explainability) and a per-stage latency breakdown.
    """
    t0 = time.perf_counter()
    success = False
    try:
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=422, detail="Query must not be empty")

        # 1. Retrieve.
        r0 = time.perf_counter()
        candidates = app_state.retriever.retrieve(query, top_k=request.top_k)
        retrieval_ms = (time.perf_counter() - r0) * 1000

        # 2. Rerank.
        rr0 = time.perf_counter()
        ranked = app_state.reranker.rerank(query, candidates, top_k=request.top_k_rerank)
        reranking_ms = (time.perf_counter() - rr0) * 1000

        # 3. Generate.
        g0 = time.perf_counter()
        generation = app_state.generator.generate(query, ranked)
        generation_ms = (time.perf_counter() - g0) * 1000

        total_ms = (time.perf_counter() - t0) * 1000
        if total_ms > settings.MAX_LATENCY_TARGET_MS:
            log.warning("latency.warning", total_ms=round(total_ms, 2))

        chunks = [
            RetrievedChunkModel(
                text=r.text,
                source_file=r.source_file,
                page_number=r.page_number,
                vector_score=round(r.score, 4),
                rerank_score=round(r.rerank_score, 4),
                rank=r.final_rank,
            )
            for r in ranked
        ]
        response = ChatResponse(
            answer=generation.answer,
            citations=[
                CitationModel(source_file=c.source_file, page_number=c.page_number)
                for c in generation.citations
            ],
            retrieved_chunks=chunks,
            latency=LatencyModel(
                retrieval_ms=round(retrieval_ms, 2),
                reranking_ms=round(reranking_ms, 2),
                generation_ms=round(generation_ms, 2),
                total_ms=round(total_ms, 2),
            ),
            model_used=generation.model_used,
        )
        success = True
        log.info(
            "chat.complete",
            query_preview=query[:50],
            total_ms=round(total_ms, 2),
            citation_count=len(response.citations),
        )
        return response
    except QdrantUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OllamaUnavailableError, OllamaModelNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        metrics_tracker.record_query((time.perf_counter() - t0) * 1000, success)
