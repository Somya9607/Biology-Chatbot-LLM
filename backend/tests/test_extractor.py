"""Tests for PDFExtractor native extraction + scanned-page detection."""
from __future__ import annotations

import fitz
import pytest

from app.ingestion.extractor import PDFExtractor


def _make_text_pdf(path: str, text: str, pages: int = 1) -> None:
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def _make_blank_pdf(path: str) -> None:
    doc = fitz.open()
    doc.new_page()  # empty page -> effectively scanned/image-only
    doc.save(path)
    doc.close()


def test_extract_native_text(tmp_path):
    pdf = str(tmp_path / "text.pdf")
    _make_text_pdf(pdf, "Mitochondria are the powerhouse of the cell. " * 5)
    pages = PDFExtractor().extract(pdf)
    assert len(pages) == 1
    assert "Mitochondria" in pages[0].text
    assert pages[0].is_scanned is False


def test_detect_scanned_page(tmp_path):
    pdf = str(tmp_path / "blank.pdf")
    _make_blank_pdf(pdf)
    pages = PDFExtractor().extract(pdf)
    assert pages[0].is_scanned is True


def test_extract_handles_corrupt_page(tmp_path, monkeypatch):
    pdf = str(tmp_path / "ok.pdf")
    _make_text_pdf(pdf, "Cell biology overview. " * 5, pages=2)

    original_load = fitz.Document.load_page

    def flaky_load(self, index):
        if index == 0:
            raise RuntimeError("simulated page error")
        return original_load(self, index)

    monkeypatch.setattr(fitz.Document, "load_page", flaky_load)
    pages = PDFExtractor().extract(pdf)
    # Both pages present; the failed page is emitted as empty/scanned.
    assert len(pages) == 2
    assert pages[0].text == ""
    assert pages[0].is_scanned is True


def test_page_numbering_is_1indexed(tmp_path):
    pdf = str(tmp_path / "multi.pdf")
    _make_text_pdf(pdf, "Genetics and inheritance patterns. " * 5, pages=3)
    pages = PDFExtractor().extract(pdf)
    assert pages[0].page_number == 1
    assert pages[-1].page_number == 3
