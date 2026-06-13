"""Tests for BiologyEmbedder. Skipped if the model cannot be loaded offline."""
from __future__ import annotations

import numpy as np
import pytest

from app.embeddings.embedder import BGE_QUERY_PREFIX, EMBEDDING_DIM


@pytest.fixture(scope="module")
def embedder():
    """Load the real embedder once; skip the module if unavailable."""
    try:
        from app.embeddings.embedder import BiologyEmbedder

        return BiologyEmbedder()
    except Exception as exc:  # noqa: BLE001 - environment without model/network
        pytest.skip(f"Embedding model unavailable: {exc}")


def test_embed_query_shape(embedder):
    vec = embedder.embed_query("What is a cell?")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (EMBEDDING_DIM,)


def test_embed_chunks_batch(embedder):
    class _C:
        def __init__(self, t):
            self.text = t

    chunks = [_C(f"biology sentence {i}") for i in range(5)]
    vecs = embedder.embed_chunks(chunks)
    assert len(vecs) == 5
    assert all(v.shape == (EMBEDDING_DIM,) for v in vecs)


def test_query_prefix_applied(embedder, monkeypatch):
    captured = {}

    def fake_encode(text, **kwargs):
        captured["text"] = text
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)

    monkeypatch.setattr(embedder.model, "encode", fake_encode)
    embedder.embed_query("mitochondria")
    assert captured["text"].startswith(BGE_QUERY_PREFIX)


def test_deterministic(embedder):
    a = embedder.embed_query("ribosome function")
    b = embedder.embed_query("ribosome function")
    np.testing.assert_allclose(a, b, rtol=1e-5, atol=1e-6)
