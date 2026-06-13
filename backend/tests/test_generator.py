"""Tests for OllamaGenerator with a mocked Ollama client."""
from __future__ import annotations

import pytest

from app.generation.generator import (
    OllamaGenerator,
    OllamaUnavailableError,
)
from app.reranking.reranker import RankedResult


def _ranked():
    return [
        RankedResult(
            chunk_id="c1",
            text="Mitochondria generate ATP via oxidative phosphorylation.",
            score=0.8,
            source_file="biology2e.pdf",
            page_number=42,
            chunk_index=3,
            pdf_id="md5abc",
            metadata={},
            rerank_score=0.95,
            original_rank=0,
            final_rank=0,
        )
    ]


class FakeClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.last_messages = None

    def chat(self, model, messages):
        self.last_messages = messages
        if self._exc:
            raise self._exc
        return self._response


def _generator_with(client) -> OllamaGenerator:
    gen = OllamaGenerator(model="mistral:7b")
    gen.client = client
    return gen


def test_citations_included_in_response():
    client = FakeClient(response={"message": {"content": "Mitochondria make energy."}})
    gen = _generator_with(client)
    result = gen.generate("What do mitochondria do?", _ranked())
    assert result.citations
    assert result.citations[0].source_file == "biology2e.pdf"
    assert result.citations[0].page_number == 42


def test_ollama_unavailable_raises_proper_error():
    client = FakeClient(exc=ConnectionError("refused"))
    gen = _generator_with(client)
    with pytest.raises(OllamaUnavailableError) as excinfo:
        gen.generate("question", _ranked())
    assert "ollama serve" in str(excinfo.value).lower()


def test_context_block_correctly_formatted():
    client = FakeClient(response={"message": {"content": "ok"}})
    gen = _generator_with(client)
    gen.generate("q", _ranked())
    user_msg = client.last_messages[1]["content"]
    assert "biology2e.pdf" in user_msg
    assert "Page 42" in user_msg


def test_response_includes_model_name():
    client = FakeClient(response={"message": {"content": "ok"}})
    gen = _generator_with(client)
    result = gen.generate("q", _ranked())
    assert result.model_used == "mistral:7b"
