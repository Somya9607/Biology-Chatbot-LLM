"""Answer generation with a local Ollama LLM (mistral:7b by default).

Builds a context block from reranked passages, sends it with a strict system
prompt to Ollama, and returns the answer plus deduplicated citations. Raises
clear, actionable errors when Ollama is down or the model is missing.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List

import httpx
import ollama

from app.config import settings
from app.logger import get_logger
from app.reranking.reranker import RankedResult

log = get_logger(__name__)

# Exact system prompt — do not alter.
SYSTEM_PROMPT = """You are BioBot, an expert biology assistant. You answer questions ONLY based on the
provided context passages from biology textbooks and study materials.

Rules:
1. Base every answer strictly on the provided context.
2. If the context does not contain enough information, say: "I don't have enough
   information in the provided materials to answer this question."
3. Always cite your sources at the end using this format:
   Sources: [filename, page X], [filename, page Y]
4. Be accurate, educational, and clear.
5. Do not hallucinate or add information not present in the context."""


class OllamaUnavailableError(RuntimeError):
    """Raised when the Ollama server cannot be reached."""


class OllamaModelNotFoundError(RuntimeError):
    """Raised when the requested Ollama model is not pulled locally."""


@dataclass
class Citation:
    """A single source reference: filename + page number."""

    source_file: str
    page_number: int


@dataclass
class GenerationResult:
    """Result of an LLM generation call with provenance and timing."""

    answer: str
    citations: List[Citation] = field(default_factory=list)
    model_used: str = ""
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


class OllamaGenerator:
    """Generate grounded answers from reranked context via Ollama."""

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or settings.OLLAMA_MODEL
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.client = ollama.Client(host=self.base_url)

    @staticmethod
    def _build_context(ranked_results: List[RankedResult]) -> str:
        """Concatenate ranked passages into a labelled context block."""
        parts = []
        for r in ranked_results:
            parts.append(
                f"--- Source: {r.source_file}, Page {r.page_number} ---\n{r.text}\n"
            )
        return "\n".join(parts)

    @staticmethod
    def _extract_citations(ranked_results: List[RankedResult]) -> List[Citation]:
        """Deduplicate citations by (source_file, page_number)."""
        seen: set[tuple[str, int]] = set()
        citations: List[Citation] = []
        for r in ranked_results:
            key = (r.source_file, r.page_number)
            if key not in seen:
                seen.add(key)
                citations.append(Citation(source_file=r.source_file, page_number=r.page_number))
        return citations

    def generate(self, query: str, ranked_results: List[RankedResult]) -> GenerationResult:
        """Generate an answer grounded in ``ranked_results`` for ``query``.

        Raises:
            OllamaUnavailableError: if the Ollama server is unreachable.
            OllamaModelNotFoundError: if the configured model is not pulled.
        """
        t0 = time.perf_counter()
        context = self._build_context(ranked_results)
        user_message = f"Context:\n{context}\n\nQuestion: {query}"

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
        except ollama.ResponseError as exc:
            if exc.status_code == 404 or "not found" in str(exc).lower():
                raise OllamaModelNotFoundError(
                    f"Model {self.model} not found. Please pull it with: "
                    f"ollama pull {self.model}"
                ) from exc
            raise OllamaUnavailableError(
                "Ollama LLM server error. Please ensure it is running: ollama serve"
            ) from exc
        except (httpx.ConnectError, httpx.TimeoutException, ConnectionError, OSError) as exc:
            raise OllamaUnavailableError(
                "Ollama LLM server is not running. Please start it with: ollama serve"
            ) from exc

        gen_ms = (time.perf_counter() - t0) * 1000
        answer = response.get("message", {}).get("content", "").strip()
        citations = self._extract_citations(ranked_results)

        log.info(
            "generation.complete",
            model=self.model,
            prompt_tokens_approx=len(user_message.split()),
            elapsed_ms=round(gen_ms, 2),
        )

        return GenerationResult(
            answer=answer,
            citations=citations,
            model_used=self.model,
            generation_latency_ms=round(gen_ms, 2),
            total_latency_ms=round(gen_ms, 2),
        )
