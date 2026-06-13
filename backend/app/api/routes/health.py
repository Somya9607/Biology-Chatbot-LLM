"""Health-check endpoints. Each returns a status JSON and never raises."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.embeddings.embedder import EMBEDDING_DIM
from app.logger import get_logger
from app.state import app_state

log = get_logger(__name__)
router = APIRouter()


@router.get("/vector-db")
async def health_vector_db() -> dict:
    """Ping Qdrant and report point count."""
    try:
        if app_state.qdrant is None:
            return {"status": "error", "points_count": 0, "message": "Qdrant not initialized"}
        if not app_state.qdrant.health_check():
            return {"status": "error", "points_count": 0, "message": "Qdrant unreachable"}
        info = app_state.qdrant.get_collection_info()
        return {"status": "ok", "points_count": info["points_count"], "message": "ok"}
    except Exception as exc:  # noqa: BLE001 - health must never raise
        log.warning("health.vector_db_failed", error=str(exc))
        return {"status": "error", "points_count": 0, "message": str(exc)}


@router.get("/llm")
async def health_llm() -> dict:
    """Ping Ollama /api/tags and report the configured model."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
        return {"status": "ok", "model": settings.OLLAMA_MODEL, "message": "ok"}
    except Exception as exc:  # noqa: BLE001
        log.warning("health.llm_failed", error=str(exc))
        return {
            "status": "error",
            "model": settings.OLLAMA_MODEL,
            "message": "Ollama not running. Start it with: ollama serve",
        }


@router.get("/ocr")
async def health_ocr() -> dict:
    """Report the installed Tesseract version."""
    try:
        import pytesseract

        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        version = str(pytesseract.get_tesseract_version())
        return {"status": "ok", "tesseract_version": version, "message": "ok"}
    except Exception as exc:  # noqa: BLE001
        log.warning("health.ocr_failed", error=str(exc))
        return {
            "status": "error",
            "tesseract_version": "",
            "message": "Tesseract not found. Install Tesseract OCR 5.x.",
        }


@router.get("/embedding")
async def health_embedding() -> dict:
    """Run a tiny test embedding and report dimensionality."""
    try:
        if app_state.embedder is None:
            return {"status": "error", "model": settings.EMBEDDING_MODEL, "dimensions": 0}
        vec = app_state.embedder.embed_query("biology test")
        return {
            "status": "ok",
            "model": settings.EMBEDDING_MODEL,
            "dimensions": int(vec.shape[0]),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("health.embedding_failed", error=str(exc))
        return {"status": "error", "model": settings.EMBEDDING_MODEL, "dimensions": 0}


@router.get("")
async def health() -> dict:
    """Aggregate health across all components."""
    components = {
        "vector_db": await health_vector_db(),
        "llm": await health_llm(),
        "ocr": await health_ocr(),
        "embedding": await health_embedding(),
    }
    statuses = [c["status"] for c in components.values()]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif all(s == "error" for s in statuses):
        overall = "error"
    else:
        overall = "degraded"
    return {"status": overall, "components": components}
