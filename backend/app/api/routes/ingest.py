"""Ingestion endpoints: index uploaded PDFs or a server-side directory."""
from __future__ import annotations

import glob
import os
import tempfile
import time
from typing import List

from fastapi import APIRouter, Request

from app.api.models import (
    IngestFileResult,
    IngestResponse,
    IngestStatusResponse,
)
from app.config import settings
from app.ingestion.fingerprint import compute_md5
from app.logger import get_logger
from app.state import app_state

log = get_logger(__name__)
router = APIRouter()


def _ingest_one(pdf_path: str) -> IngestFileResult:
    """Run the full ingestion pipeline for a single PDF on disk."""
    filename = os.path.basename(pdf_path)

    # 1. Fingerprint check (idempotent ingestion).
    if app_state.fingerprints.is_indexed(pdf_path):
        return IngestFileResult(
            filename=filename, status="skipped", chunks_created=0,
            message="Already indexed (fingerprint match)",
        )

    try:
        # 2. Extract.
        pages = app_state.extractor.extract(pdf_path)

        # 3. OCR scanned pages only.
        scanned = [p.page_number for p in pages if p.is_scanned]
        if scanned:
            ocr_texts = app_state.ocr.process_scanned_pages(pdf_path, scanned)
            for p in pages:
                if p.is_scanned:
                    p.text = ocr_texts.get(p.page_number, "")

        # 4. Clean.
        for p in pages:
            p.text = app_state.cleaner.clean(p.text, p.page_number, p.source_file)

        # 5. Chunk.
        pdf_id = compute_md5(pdf_path)
        chunks = app_state.chunker.chunk_pages(pages, filename, pdf_id)
        if not chunks:
            return IngestFileResult(
                filename=filename, status="error", chunks_created=0,
                message="No extractable text produced any chunks",
            )

        # 6. Embed.
        embeddings = app_state.embedder.embed_chunks(chunks)

        # 7. Upsert.
        count = app_state.qdrant.upsert_chunks(chunks, embeddings)

        # 8. Mark indexed.
        app_state.fingerprints.mark_indexed(pdf_path, {"chunk_count": count})

        log.info("ingestion.complete", filename=filename, chunks_created=count)
        return IngestFileResult(
            filename=filename, status="indexed", chunks_created=count,
            message=f"Indexed {count} chunks",
        )
    except Exception as exc:  # noqa: BLE001 - report per-file, keep batch going
        log.error("ingestion.failed", filename=filename, error=str(exc))
        return IngestFileResult(
            filename=filename, status="error", chunks_created=0, message=str(exc),
        )


@router.post("", response_model=IngestResponse)
async def ingest(request: Request) -> IngestResponse:
    """Ingest uploaded PDF files (multipart) or a server-side directory (JSON).

    The endpoint branches on the request ``Content-Type``:

    * ``multipart/form-data`` -> read uploaded ``files`` and ingest each.
    * anything else (JSON / empty) -> read ``pdf_dir`` and ingest every PDF
      in that server-side directory (falls back to ``settings.PDF_DIR``).
    """
    t0 = time.perf_counter()
    results: List[IngestFileResult] = []
    temp_paths: List[str] = []
    content_type = request.headers.get("content-type", "")

    try:
        pdf_paths: List[str] = []

        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            uploads = form.getlist("files")
            for upload in uploads:
                filename = getattr(upload, "filename", None)
                if not filename or not filename.lower().endswith(".pdf"):
                    results.append(
                        IngestFileResult(
                            filename=filename or "unknown", status="error",
                            chunks_created=0, message="Not a PDF file",
                        )
                    )
                    continue
                tmp = os.path.join(tempfile.gettempdir(), os.path.basename(filename))
                with open(tmp, "wb") as fh:
                    fh.write(await upload.read())
                temp_paths.append(tmp)
                pdf_paths.append(tmp)
        else:
            pdf_dir = settings.PDF_DIR
            try:
                payload = await request.json()
                if isinstance(payload, dict) and payload.get("pdf_dir"):
                    pdf_dir = payload["pdf_dir"]
            except (ValueError, TypeError):
                pass
            pdf_paths.extend(sorted(glob.glob(os.path.join(pdf_dir, "*.pdf"))))

        for path in pdf_paths:
            results.append(_ingest_one(path))
    finally:
        for tmp in temp_paths:
            try:
                os.remove(tmp)
            except OSError:
                pass

    return IngestResponse(
        results=results,
        total_indexed=sum(1 for r in results if r.status == "indexed"),
        total_skipped=sum(1 for r in results if r.status == "skipped"),
        total_errors=sum(1 for r in results if r.status == "error"),
        elapsed_seconds=round(time.perf_counter() - t0, 2),
    )


@router.post("/status", response_model=IngestStatusResponse)
async def ingest_status() -> IngestStatusResponse:
    """Return the indexed-document registry and total chunk count in the DB."""
    indexed = app_state.fingerprints.get_all_indexed()
    documents = [
        {"md5": md5, **meta} for md5, meta in indexed.items()
    ]
    total_chunks = 0
    if app_state.qdrant is not None:
        total_chunks = app_state.qdrant.get_collection_info().get("points_count", 0)
    return IngestStatusResponse(
        indexed_documents=documents, total_chunks_in_db=total_chunks,
    )
