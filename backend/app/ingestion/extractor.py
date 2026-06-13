"""Native PDF text extraction with scanned-page detection.

Primary engine is PyMuPDF (``fitz``). Pages whose native text is shorter than
a threshold (50 chars after stripping) are flagged as scanned so the OCR stage
can process only those pages. A pdfminer.six fallback is available for whole
documents that PyMuPDF cannot open.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

import fitz  # PyMuPDF

from app.logger import get_logger

log = get_logger(__name__)

# Pages with fewer characters than this (after stripping) are treated as
# scanned/image-only and routed to OCR.
SCANNED_TEXT_THRESHOLD = 50


@dataclass
class PageContent:
    """Extracted content for a single PDF page (1-indexed page numbers)."""

    page_number: int
    text: str
    is_scanned: bool
    source_file: str
    bounding_boxes: Optional[List[dict]] = field(default=None)


class PDFExtractor:
    """Extract per-page text from a PDF using PyMuPDF, flagging scanned pages."""

    def _is_page_scanned(self, text: str) -> bool:
        """A page is scanned if its stripped native text is below threshold."""
        return len(text.strip()) < SCANNED_TEXT_THRESHOLD

    def extract(self, pdf_path: str) -> List[PageContent]:
        """Extract text from every page of ``pdf_path``.

        Per-page extraction errors are caught and logged; the page is emitted
        as scanned with empty text so the pipeline can continue.

        Args:
            pdf_path: Filesystem path to the PDF.

        Returns:
            A list of :class:`PageContent`, one per page, ordered by page.
        """
        source_file = os.path.basename(pdf_path)
        pages: List[PageContent] = []
        scanned_count = 0

        try:
            doc = fitz.open(pdf_path)
        except (fitz.FileDataError, RuntimeError, OSError) as exc:
            log.error("ingestion.extract_open_failed", filename=source_file, error=str(exc))
            raise

        try:
            for index in range(doc.page_count):
                page_number = index + 1
                try:
                    page = doc.load_page(index)
                    text = page.get_text("text")
                    boxes = self._extract_boxes(page)
                    is_scanned = self._is_page_scanned(text)
                    if is_scanned:
                        scanned_count += 1
                    pages.append(
                        PageContent(
                            page_number=page_number,
                            text=text,
                            is_scanned=is_scanned,
                            source_file=source_file,
                            bounding_boxes=boxes,
                        )
                    )
                except (RuntimeError, ValueError) as exc:
                    log.warning(
                        "ingestion.extract_page_failed",
                        filename=source_file,
                        page_number=page_number,
                        error=str(exc),
                    )
                    pages.append(
                        PageContent(
                            page_number=page_number,
                            text="",
                            is_scanned=True,
                            source_file=source_file,
                            bounding_boxes=None,
                        )
                    )
        finally:
            doc.close()

        log.info(
            "ingestion.extract",
            filename=source_file,
            total_pages=len(pages),
            scanned_pages_count=scanned_count,
        )
        return pages

    @staticmethod
    def _extract_boxes(page: "fitz.Page") -> Optional[List[dict]]:
        """Return text-block bounding boxes from a page, or None on failure."""
        try:
            blocks = page.get_text("blocks")
            return [
                {"x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3]}
                for b in blocks
            ]
        except (RuntimeError, ValueError):
            return None
