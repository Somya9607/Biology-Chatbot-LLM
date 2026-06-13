"""API tests using FastAPI TestClient with all heavy components stubbed."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.generation.generator import Citation, GenerationResult
from app.reranking.reranker import RankedResult
from tests.conftest import make_search_result


# --- Stubs for the startup lifespan ----------------------------------------
class StubEmbedder:
    def embed_query(self, query):
        return np.ones(384, dtype=np.float32)

    def embed_chunks(self, chunks):
        return [np.ones(384, dtype=np.float32) for _ in chunks]


class StubReranker:
    def rerank(self, query, results, top_k=4):
        out = []
        for i, r in enumerate(results[:top_k]):
            out.append(
                RankedResult(
                    chunk_id=r.chunk_id, text=r.text, score=r.score,
                    source_file=r.source_file, page_number=r.page_number,
                    chunk_index=r.chunk_index, pdf_id=r.pdf_id, metadata=r.metadata,
                    rerank_score=0.9 - i * 0.1, original_rank=i, final_rank=i,
                )
            )
        return out


class StubQdrant:
    def ensure_collection(self):
        return None

    def health_check(self):
        return True

    def get_collection_info(self):
        return {"points_count": 5, "collection_name": "biology_rag", "status": "green"}

    def search(self, query_vector, top_k=10):
        return [make_search_result(f"chunk {i}", score=0.9 - i * 0.1, page=i + 1) for i in range(3)]


class StubRetriever:
    def retrieve(self, query, top_k=10):
        return [make_search_result(f"chunk {i}", score=0.9 - i * 0.1, page=i + 1) for i in range(3)]


class StubGenerator:
    model = "mistral:7b"

    def generate(self, query, ranked):
        return GenerationResult(
            answer="Mitochondria are the powerhouse of the cell.",
            citations=[Citation(source_file="bio.pdf", page_number=1)],
            model_used="mistral:7b",
            generation_latency_ms=10.0,
            total_latency_ms=10.0,
        )


class StubFingerprints:
    def __init__(self, indexed=False):
        self._indexed = indexed

    def is_indexed(self, path):
        return self._indexed

    def mark_indexed(self, path, meta):
        return None

    def get_all_indexed(self):
        return {"md5abc": {"filename": "bio.pdf", "indexed_at": "now", "chunk_count": 5}}


@pytest.fixture
def client(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "BiologyEmbedder", lambda *a, **k: StubEmbedder())
    monkeypatch.setattr(main, "CrossEncoderReranker", lambda *a, **k: StubReranker())
    monkeypatch.setattr(main, "QdrantManager", lambda *a, **k: StubQdrant())
    monkeypatch.setattr(main, "OllamaGenerator", lambda *a, **k: StubGenerator())
    monkeypatch.setattr(main, "BiologyRetriever", lambda *a, **k: StubRetriever())

    with TestClient(main.app) as c:
        # Ensure deterministic components regardless of lifespan wiring.
        from app.state import app_state

        app_state.retriever = StubRetriever()
        app_state.reranker = StubReranker()
        app_state.generator = StubGenerator()
        app_state.qdrant = StubQdrant()
        app_state.embedder = StubEmbedder()
        app_state.fingerprints = StubFingerprints(indexed=False)
        yield c


def test_health_endpoint_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "components" in resp.json()


def test_health_vector_db_endpoint(client):
    resp = client.get("/health/vector-db")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["points_count"] == 5


def test_health_llm_endpoint(client):
    resp = client.get("/health/llm")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_chat_endpoint_returns_answer(client):
    resp = client.post("/chat", json={"query": "What is mitochondria?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "powerhouse" in body["answer"]
    assert len(body["citations"]) >= 1
    assert "total_ms" in body["latency"]


def test_chat_empty_query_returns_422(client):
    resp = client.post("/chat", json={"query": ""})
    assert resp.status_code == 422


def test_ingest_endpoint_skips_already_indexed(client, tmp_path):
    from app.state import app_state

    app_state.fingerprints = StubFingerprints(indexed=True)
    pdf = tmp_path / "already.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    resp = client.post("/ingest", json={"pdf_dir": str(tmp_path)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_skipped"] == 1
    assert body["results"][0]["status"] == "skipped"


def test_metrics_endpoint_returns_stats(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "p95_latency_ms" in resp.json()
