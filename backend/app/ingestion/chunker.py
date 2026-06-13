"""Token-based text chunking with overlap, using tiktoken (cl100k_base).

Chunks are built per page so that every chunk carries an accurate page number
for citations. Within a page, sentences are greedily packed up to
``CHUNK_SIZE`` tokens with a sliding ``CHUNK_OVERLAP`` carried into the next
chunk, avoiding mid-sentence splits where possible.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List

import regex as re
import tiktoken

from app.config import settings
from app.ingestion.extractor import PageContent
from app.logger import get_logger

log = get_logger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")
# Split on sentence terminators followed by whitespace, or blank lines.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


@dataclass
class ChunkData:
    """A single retrievable chunk with citation metadata."""

    chunk_id: str
    text: str
    token_count: int
    source_file: str
    page_number: int
    chunk_index: int
    metadata: dict = field(default_factory=dict)


class TextChunker:
    """Greedy sentence-aware, token-bounded chunker with overlap."""

    def __init__(
        self, chunk_size: int | None = None, chunk_overlap: int | None = None
    ) -> None:
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def _count_tokens(self, text: str) -> int:
        """Return the number of cl100k_base tokens in ``text``."""
        return len(_ENCODING.encode(text))

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentence-ish units; drop empties."""
        return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]

    def _overlap_sentences(self, sentences: List[str]) -> List[str]:
        """Return a trailing slice of sentences within the overlap token budget."""
        overlap: List[str] = []
        tokens = 0
        for sentence in reversed(sentences):
            t = self._count_tokens(sentence)
            if tokens + t > self.chunk_overlap and overlap:
                break
            overlap.insert(0, sentence)
            tokens += t
        return overlap

    def chunk_pages(
        self, pages: List[PageContent], source_file: str, pdf_id: str
    ) -> List[ChunkData]:
        """Chunk a list of pages into :class:`ChunkData` with metadata.

        Args:
            pages: Per-page extracted/cleaned content.
            source_file: PDF filename (used in metadata + citations).
            pdf_id: MD5 fingerprint of the source PDF.

        Returns:
            All chunks across all pages, with a document-sequential index.
        """
        chunks: List[ChunkData] = []
        chunk_index = 0
        total_tokens = 0

        for page in pages:
            text = (page.text or "").strip()
            if not text:
                continue

            sentences = self._split_sentences(text)
            if not sentences:
                continue

            current: List[str] = []
            current_tokens = 0

            for sentence in sentences:
                s_tokens = self._count_tokens(sentence)
                # If a single sentence exceeds chunk_size, emit it on its own.
                if s_tokens >= self.chunk_size:
                    if current:
                        chunk_index, total_tokens = self._emit(
                            chunks, current, source_file, page.page_number,
                            pdf_id, chunk_index, total_tokens,
                        )
                        current, current_tokens = [], 0
                    chunk_index, total_tokens = self._emit(
                        chunks, [sentence], source_file, page.page_number,
                        pdf_id, chunk_index, total_tokens,
                    )
                    continue

                if current_tokens + s_tokens > self.chunk_size and current:
                    chunk_index, total_tokens = self._emit(
                        chunks, current, source_file, page.page_number,
                        pdf_id, chunk_index, total_tokens,
                    )
                    # Slide back by overlap for the next chunk.
                    current = self._overlap_sentences(current)
                    current_tokens = sum(self._count_tokens(s) for s in current)

                current.append(sentence)
                current_tokens += s_tokens

            if current:
                chunk_index, total_tokens = self._emit(
                    chunks, current, source_file, page.page_number,
                    pdf_id, chunk_index, total_tokens,
                )

        avg = (total_tokens / len(chunks)) if chunks else 0
        log.info(
            "chunking.complete",
            source_file=source_file,
            total_chunks=len(chunks),
            avg_chunk_size=round(avg, 1),
        )
        return chunks

    def _emit(
        self,
        chunks: List[ChunkData],
        sentences: List[str],
        source_file: str,
        page_number: int,
        pdf_id: str,
        chunk_index: int,
        total_tokens: int,
    ) -> tuple[int, int]:
        """Build a ChunkData from accumulated sentences and append it."""
        text = " ".join(sentences).strip()
        token_count = self._count_tokens(text)
        chunk = ChunkData(
            chunk_id=str(uuid.uuid4()),
            text=text,
            token_count=token_count,
            source_file=source_file,
            page_number=page_number,
            chunk_index=chunk_index,
            metadata={
                "pdf_id": pdf_id,
                "filename": source_file,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "token_count": token_count,
            },
        )
        chunks.append(chunk)
        return chunk_index + 1, total_tokens + token_count
