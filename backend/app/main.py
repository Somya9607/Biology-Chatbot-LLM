"""FastAPI application entry point.

Loads heavy ML components once at startup (embedder, reranker, Qdrant,
retriever, generator), wires the API routers, configures permissive CORS for
local dev + Vercel, and installs a global exception handler.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat as chat_routes
from app.api.routes import health as health_routes
from app.api.routes import ingest as ingest_routes
from app.embeddings.embedder import BiologyEmbedder
from app.generation.generator import OllamaGenerator
from app.ingestion.chunker import TextChunker
from app.ingestion.cleaner import TextCleaner
from app.ingestion.extractor import PDFExtractor
from app.ingestion.fingerprint import DocumentFingerprintManager
from app.ingestion.ocr import OCRProcessor
from app.logger import configure_logging, get_logger
from app.monitoring.metrics import metrics_tracker
from app.reranking.reranker import CrossEncoderReranker
from app.retrieval.retriever import BiologyRetriever
from app.state import app_state
from app.vectordb.qdrant_client import QdrantManager, QdrantUnavailableError

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all components on startup; log component statuses."""
    configure_logging()
    statuses: dict[str, str] = {}

    # Lightweight ingestion components.
    app_state.extractor = PDFExtractor()
    app_state.ocr = OCRProcessor()
    app_state.cleaner = TextCleaner()
    app_state.chunker = TextChunker()
    app_state.fingerprints = DocumentFingerprintManager()

    # Embedder (downloads model on first run).
    try:
        app_state.embedder = BiologyEmbedder()
        statuses["embedder"] = "ok"
    except Exception as exc:  # noqa: BLE001
        log.error("startup.embedder_failed", error=str(exc))
        statuses["embedder"] = "error"

    # Reranker.
    try:
        app_state.reranker = CrossEncoderReranker()
        statuses["reranker"] = "ok"
    except Exception as exc:  # noqa: BLE001
        log.error("startup.reranker_failed", error=str(exc))
        statuses["reranker"] = "error"

    # Qdrant (object always created; connection verified via ensure_collection).
    try:
        app_state.qdrant = QdrantManager()
        app_state.qdrant.ensure_collection()
        statuses["qdrant"] = "ok"
    except QdrantUnavailableError as exc:
        log.error("startup.qdrant_unavailable", error=str(exc))
        statuses["qdrant"] = "error"
        if app_state.qdrant is None:
            # Still create the object so query-time raises a clean 503.
            try:
                app_state.qdrant = QdrantManager()
            except QdrantUnavailableError:
                app_state.qdrant = None

    # Retriever (composes embedder + qdrant).
    if app_state.embedder is not None and app_state.qdrant is not None:
        app_state.retriever = BiologyRetriever(app_state.embedder, app_state.qdrant)
        statuses["retriever"] = "ok"
    else:
        statuses["retriever"] = "error"

    # Generator (client only; no network call at startup).
    app_state.generator = OllamaGenerator()
    statuses["generator"] = "ok"

    log.info("startup.complete", components=statuses)
    yield
    log.info("shutdown.complete")


app = FastAPI(title="Biology RAG Chatbot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_routes.router, prefix="/health", tags=["health"])
app.include_router(ingest_routes.router, prefix="/ingest", tags=["ingest"])
app.include_router(chat_routes.router, prefix="/chat", tags=["chat"])


@app.get("/metrics", tags=["metrics"])
async def metrics() -> dict:
    """Return in-memory query/latency/error statistics."""
    return metrics_tracker.get_stats()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a uniform error envelope for unhandled exceptions."""
    log.error("unhandled_exception", path=str(request.url.path), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
