"""Text cleaning and normalization for extracted PDF page text.

The cleaning pipeline is intentionally conservative: it normalizes unicode,
strips control characters, collapses whitespace, repairs hyphenation at line
breaks, removes obvious page-number lines, and detects the document language.
It never raises; on any unexpected error it logs a warning and returns the
best-effort result.
"""
from __future__ import annotations

import unicodedata

import regex as re
from langdetect import DetectorFactory, LangDetectException, detect

from app.logger import get_logger

log = get_logger(__name__)

# Deterministic language detection across runs.
DetectorFactory.seed = 0

# Control chars to strip, preserving tab and newline.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_PURE_NUMERIC_LINE = re.compile(r"^\s*\d{1,4}\s*$")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


class TextCleaner:
    """Normalize and clean raw extracted page text."""

    def detect_language(self, text: str) -> str:
        """Return an ISO 639-1 language code, or 'unknown' if undetectable."""
        sample = text.strip()
        if len(sample) < 20:
            return "unknown"
        try:
            return detect(sample)
        except LangDetectException:
            return "unknown"

    def clean(self, text: str, page_number: int, source_file: str) -> str:
        """Run the full cleaning pipeline over a single page's text.

        Args:
            text: Raw extracted page text.
            page_number: 1-indexed page number (for logging context).
            source_file: PDF filename (for logging context).

        Returns:
            Cleaned text. Never raises.
        """
        if not text:
            return ""

        try:
            # 1. Normalize unicode to NFC.
            cleaned = unicodedata.normalize("NFC", text)

            # 2. Remove null bytes / control chars (keep \n, \t).
            cleaned = _CONTROL_CHARS.sub("", cleaned)

            # 5. Repair hyphenation across line breaks: "exam-\nple" -> "example".
            cleaned = _HYPHEN_BREAK.sub(r"\1\2", cleaned)

            # 4. Drop lines that are purely a page number.
            lines = cleaned.split("\n")
            kept = [ln for ln in lines if not _PURE_NUMERIC_LINE.match(ln)]
            cleaned = "\n".join(kept)

            # 3. Collapse repeated spaces/tabs.
            cleaned = _MULTI_SPACE.sub(" ", cleaned)

            # 6. Normalize 3+ newlines down to 2.
            cleaned = _MULTI_NEWLINE.sub("\n\n", cleaned)

            # 8. Strip leading/trailing whitespace.
            cleaned = cleaned.strip()

            # 7. Detect language; warn if not English but keep the text.
            lang = self.detect_language(cleaned)
            if lang not in ("en", "unknown"):
                log.warning(
                    "cleaning.non_english",
                    filename=source_file,
                    page_number=page_number,
                    detected_language=lang,
                )

            return cleaned
        except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
            log.warning(
                "cleaning.failed",
                filename=source_file,
                page_number=page_number,
                error=str(exc),
            )
            return text.strip() if text else ""
