"""OCR for scanned PDF pages using Tesseract (via pytesseract) and OCRmyPDF.

Only pages flagged ``is_scanned`` by the extractor are processed. Two
strategies are available:

* **Per-page** (default): render each scanned page to a 2x image with PyMuPDF
  and run pytesseract on it. Cheap when only a handful of pages are scanned.
* **Full-document**: run ``ocrmypdf --skip-text`` over the whole PDF, then
  re-extract. Preferred when the majority of pages are scanned.

OCR failures on a single page never abort the run: the error is logged and an
empty string is returned for that page.
"""
from __future__ import annotations

import io
import os
import subprocess
import tempfile
from typing import Dict, List

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.logger import get_logger

log = get_logger(__name__)

# If at least this fraction of pages are scanned, prefer full-document OCRmyPDF.
FULL_OCR_THRESHOLD = 0.5


class OCRProcessor:
    """Run OCR over the scanned pages of a PDF."""

    def process_scanned_pages(
        self, pdf_path: str, scanned_pages: List[int]
    ) -> Dict[int, str]:
        """OCR the given (1-indexed) scanned page numbers.

        Args:
            pdf_path: Path to the source PDF.
            scanned_pages: 1-indexed page numbers needing OCR.

        Returns:
            Mapping of page_number -> extracted text (empty string on failure).
        """
        if not scanned_pages:
            return {}

        source_file = os.path.basename(pdf_path)
        results: Dict[int, str] = {}

        # Decide strategy based on how many pages need OCR.
        try:
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            doc.close()
        except (fitz.FileDataError, RuntimeError, OSError) as exc:
            log.error("ocr.open_failed", filename=source_file, error=str(exc))
            return {p: "" for p in scanned_pages}

        use_full = total_pages > 0 and (len(scanned_pages) / total_pages) >= FULL_OCR_THRESHOLD

        if use_full:
            ocr_pdf = self._ocrmypdf_full(pdf_path)
            if ocr_pdf:
                results = self._reextract_pages(ocr_pdf, scanned_pages, source_file)
                # Fill any gaps with per-page OCR fallback.
                missing = [p for p in scanned_pages if not results.get(p, "").strip()]
                for page_num in missing:
                    results[page_num] = self._tesseract_page(pdf_path, page_num)
                return results

        # Per-page strategy.
        for page_num in scanned_pages:
            results[page_num] = self._tesseract_page(pdf_path, page_num)
        return results

    def _tesseract_page(self, pdf_path: str, page_num: int) -> str:
        """Render a single page to a 2x image and OCR it with pytesseract."""
        source_file = os.path.basename(pdf_path)
        try:
            doc = fitz.open(pdf_path)
            try:
                page = doc.load_page(page_num - 1)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(image, lang="eng")
            finally:
                doc.close()
        except (pytesseract.TesseractError, RuntimeError, OSError, ValueError) as exc:
            log.warning(
                "ocr.process",
                filename=source_file,
                page_number=page_num,
                method_used="tesseract",
                error=str(exc),
                char_count_extracted=0,
            )
            return ""

        log.info(
            "ocr.process",
            filename=source_file,
            page_number=page_num,
            method_used="tesseract",
            char_count_extracted=len(text),
        )
        return text

    def _ocrmypdf_full(self, pdf_path: str) -> str:
        """Run ``ocrmypdf --skip-text`` over the full PDF; return output path.

        Returns an empty string if OCRmyPDF is unavailable or fails.
        """
        source_file = os.path.basename(pdf_path)
        out_path = os.path.join(
            tempfile.gettempdir(), f"ocr_{os.path.splitext(source_file)[0]}.pdf"
        )
        try:
            subprocess.run(
                ["ocrmypdf", "--skip-text", "--quiet", pdf_path, out_path],
                check=True,
                capture_output=True,
                timeout=1800,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            log.warning(
                "ocr.ocrmypdf_failed",
                filename=source_file,
                error=str(exc),
            )
            return ""

        log.info("ocr.ocrmypdf_complete", filename=source_file, output=out_path)
        return out_path

    def _reextract_pages(
        self, ocr_pdf_path: str, pages: List[int], source_file: str
    ) -> Dict[int, str]:
        """Re-extract native text from an OCR'd PDF for the given pages."""
        results: Dict[int, str] = {}
        try:
            doc = fitz.open(ocr_pdf_path)
            try:
                for page_num in pages:
                    if 1 <= page_num <= doc.page_count:
                        text = doc.load_page(page_num - 1).get_text("text")
                        results[page_num] = text
                        log.info(
                            "ocr.process",
                            filename=source_file,
                            page_number=page_num,
                            method_used="ocrmypdf",
                            char_count_extracted=len(text),
                        )
                    else:
                        results[page_num] = ""
            finally:
                doc.close()
        except (fitz.FileDataError, RuntimeError, OSError) as exc:
            log.warning("ocr.reextract_failed", filename=source_file, error=str(exc))
            return {p: "" for p in pages}
        return results
