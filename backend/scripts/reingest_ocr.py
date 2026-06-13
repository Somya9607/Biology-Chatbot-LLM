"""Re-ingest specific PDFs with OCR enabled, replacing any stale chunks.

For each target file this:
  1. computes its MD5,
  2. deletes existing Qdrant points for that pdf_id (avoids duplicates),
  3. removes its fingerprint entry (so it is no longer 'already indexed'),
  4. runs the full ingestion pipeline again — now with Tesseract OCR available.

Usage (from backend/):
    python scripts/reingest_ocr.py "11th combined NCERT SMASHER_2.0.pdf" "NCERT SMASHER 2.0 [12th Combine].pdf"
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from qdrant_client.http import models as qmodels  # noqa: E402

from app.config import settings  # noqa: E402
from app.embeddings.embedder import BiologyEmbedder  # noqa: E402
from app.ingestion.chunker import TextChunker  # noqa: E402
from app.ingestion.cleaner import TextCleaner  # noqa: E402
from app.ingestion.extractor import PDFExtractor  # noqa: E402
from app.ingestion.fingerprint import DocumentFingerprintManager, compute_md5  # noqa: E402
from app.ingestion.ocr import OCRProcessor  # noqa: E402
from app.vectordb.qdrant_client import QdrantManager  # noqa: E402


def _delete_existing(qdrant: QdrantManager, pdf_id: str) -> None:
    """Delete all points belonging to a given pdf_id."""
    qdrant.client.delete(
        collection_name=qdrant.collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="pdf_id", match=qmodels.MatchValue(value=pdf_id))]
            )
        ),
    )


def _clear_fingerprint(pdf_id: str) -> None:
    """Remove a pdf_id entry from the fingerprint registry, if present."""
    path = settings.FINGERPRINT_FILE
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if pdf_id in data:
        del data[pdf_id]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)


def main(filenames: list[str]) -> None:
    print(f"Tesseract: {settings.TESSERACT_CMD or '(PATH)'}")
    embedder = BiologyEmbedder()
    qdrant = QdrantManager()
    qdrant.ensure_collection()
    fingerprints = DocumentFingerprintManager()
    extractor, ocr, cleaner, chunker = PDFExtractor(), OCRProcessor(), TextCleaner(), TextChunker()

    for name in filenames:
        pdf_path = os.path.join(settings.PDF_DIR, name)
        if not os.path.exists(pdf_path):
            print(f"  !! not found: {pdf_path}")
            continue

        pdf_id = compute_md5(pdf_path)
        print(f"Re-ingesting (OCR): {name}")
        _delete_existing(qdrant, pdf_id)
        _clear_fingerprint(pdf_id)

        pages = extractor.extract(pdf_path)
        scanned = [p.page_number for p in pages if p.is_scanned]
        print(f"  scanned pages to OCR: {len(scanned)} / {len(pages)}")
        if scanned:
            ocr_texts = ocr.process_scanned_pages(pdf_path, scanned)
            for p in pages:
                if p.is_scanned:
                    p.text = ocr_texts.get(p.page_number, "")
        for p in pages:
            p.text = cleaner.clean(p.text, p.page_number, p.source_file)

        chunks = chunker.chunk_pages(pages, name, pdf_id)
        embeddings = embedder.embed_chunks(chunks)
        count = qdrant.upsert_chunks(chunks, embeddings)
        fingerprints.mark_indexed(pdf_path, {"chunk_count": count})
        print(f"  -> Indexed {count} chunks (was much lower before OCR)")

    print("OCR re-ingestion complete!")


if __name__ == "__main__":
    targets = sys.argv[1:] or [
        "11th combined NCERT SMASHER_2.0.pdf",
        "NCERT SMASHER 2.0 [12th Combine].pdf",
    ]
    main(targets)
