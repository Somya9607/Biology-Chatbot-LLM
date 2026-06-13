"""Ingest all PDFs in ``sample_pdfs/`` directly through the pipeline.

Used by the demo launchers (start_demo.sh / start_demo.ps1) to seed the vector
DB before the API comes up. Idempotent: already-indexed PDFs are skipped via
their fingerprint. Run from the ``backend/`` directory.
"""
from __future__ import annotations

import glob
import os
import sys

# Allow running as a plain script from the backend directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.embeddings.embedder import BiologyEmbedder  # noqa: E402
from app.ingestion.chunker import TextChunker  # noqa: E402
from app.ingestion.cleaner import TextCleaner  # noqa: E402
from app.ingestion.extractor import PDFExtractor  # noqa: E402
from app.ingestion.fingerprint import (  # noqa: E402
    DocumentFingerprintManager,
    compute_md5,
)
from app.ingestion.ocr import OCRProcessor  # noqa: E402
from app.vectordb.qdrant_client import QdrantManager  # noqa: E402


def main(pdf_glob: str = "./sample_pdfs/*.pdf") -> None:
    """Run the full ingestion pipeline over every PDF matching ``pdf_glob``."""
    pdfs = sorted(glob.glob(pdf_glob))
    print(f"Found {len(pdfs)} sample PDFs")

    embedder = BiologyEmbedder()
    qdrant = QdrantManager()
    qdrant.ensure_collection()
    fingerprints = DocumentFingerprintManager()
    extractor = PDFExtractor()
    ocr = OCRProcessor()
    cleaner = TextCleaner()
    chunker = TextChunker()

    for pdf_path in pdfs:
        name = os.path.basename(pdf_path)
        if fingerprints.is_indexed(pdf_path):
            print(f"  -> Skipping (already indexed): {name}")
            continue

        print(f"Processing: {name}")
        pages = extractor.extract(pdf_path)

        scanned = [p.page_number for p in pages if p.is_scanned]
        if scanned:
            ocr_texts = ocr.process_scanned_pages(pdf_path, scanned)
            for p in pages:
                if p.is_scanned:
                    p.text = ocr_texts.get(p.page_number, "")

        for p in pages:
            p.text = cleaner.clean(p.text, p.page_number, p.source_file)

        pdf_id = compute_md5(pdf_path)
        chunks = chunker.chunk_pages(pages, name, pdf_id)
        embeddings = embedder.embed_chunks(chunks)
        count = qdrant.upsert_chunks(chunks, embeddings)
        fingerprints.mark_indexed(pdf_path, {"chunk_count": count})
        print(f"  -> Indexed {count} chunks")

    print("Ingestion complete!")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "./sample_pdfs/*.pdf"
    main(target)
