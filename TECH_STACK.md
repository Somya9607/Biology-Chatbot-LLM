# Technology Stack Reference

Every component is free and open-source and runs locally. Versions are pinned in
`backend/requirements.txt` and `frontend/package.json`.

## Backend

| Library | Version | Purpose | Why Chosen |
|---|---|---|---|
| fastapi | 0.111.0 | Web framework / API | Mature, async, single-app, auto OpenAPI docs |
| uvicorn[standard] | 0.29.0 | ASGI server | Fast, production-ready, supports `--reload` |
| pymupdf (fitz) | 1.24.3 | Native PDF text extraction | Best-in-class OSS extraction quality + speed |
| pdfminer.six | 20231228 | Secondary PDF extraction | Pure-Python fallback for tricky PDFs |
| pytesseract | 0.3.10 | OCR (per-page) | Thin, stable wrapper over Tesseract |
| ocrmypdf | 15.4.4 | Full-document OCR | Robust scanned-PDF OCR via Tesseract |
| Pillow | 10.3.0 | Image handling | Render pages to images for OCR |
| langdetect | 1.0.9 | Language detection | Lightweight, deterministic (seeded) |
| regex | 2024.4.16 | Text normalization | Unicode-aware, richer than stdlib `re` |
| tiktoken | 0.7.0 | Token counting / chunking | Accurate `cl100k_base` token boundaries |
| sentence-transformers | 2.7.0 | Embeddings + reranker | Standard for BGE + cross-encoder models |
| qdrant-client | 1.9.1 | Vector DB client | HNSW ANN, payload filtering, local Docker |
| ollama | 0.2.1 | Local LLM client | No API key, runs models locally |
| structlog | 24.1.0 | Structured JSON logging | Machine-parseable, contextual logs |
| pydantic | 2.7.1 | Data models / validation | Type-safe request/response models |
| pydantic-settings | 2.2.1 | Configuration | Env-driven, type-safe settings |
| httpx | 0.27.0 | Async HTTP | Health checks, test client |
| numpy | 1.26.4 | Numerics | Float32 embedding vectors |
| tqdm | 4.66.4 | Progress bars | Embedding batch progress |
| python-multipart | 0.0.9 | File uploads | Multipart parsing for `/ingest` |
| pytest / pytest-asyncio | 8.2.0 / 0.23.6 | Testing | Full unit + integration suite |

## Frontend

| Library | Version | Purpose |
|---|---|---|
| next | 14.2.3 | React framework (App Router) |
| react / react-dom | 18.3.1 | UI runtime |
| axios | 1.7.2 | HTTP client |
| lucide-react | 0.379.0 | Icons |
| react-markdown | 9.0.1 | Render assistant markdown |
| react-syntax-highlighter | 15.5.0 | Code block highlighting |
| tailwindcss | 3.4.3 | Styling |
| autoprefixer / postcss | 10.4.19 / 8.4.38 | CSS tooling |
| typescript | 5.4.5 | Type safety |

## Infrastructure

| Tool | Version | Purpose |
|---|---|---|
| Qdrant | v1.9.2 (Docker) | Vector database (HNSW, cosine) |
| Ollama | local binary | LLM serving |
| Docker + docker-compose | — | Run Qdrant locally |
| Tesseract OCR | 5.x | OCR engine |

## AI/ML Models

| Model | Source | Purpose | Size / Dimensions |
|---|---|---|---|
| BAAI/bge-small-en-v1.5 | Hugging Face | Embedding | 384-dim, ~33M params |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | Hugging Face | Reranking | ~22M params |
| mistral:7b (default) / llama3:8b | Ollama | Generation | 7–8B params, runs on 8 GB RAM |

## Data Flow

```
Ingestion:
  PDF ─► Extract (PyMuPDF) ─► OCR if scanned (Tesseract) ─► Clean (normalize,
        strip headers/footers, de-hyphenate) ─► Chunk (750 tok / 150 overlap,
        tiktoken) ─► Embed (BGE-small) ─► Qdrant upsert (with page metadata)

Query:
  Question ─► Embed (BGE query prefix) ─► Qdrant ANN search (top-10) ─►
        Cross-encoder rerank (top-4) ─► Ollama LLM ─► Answer + citations
```

## Design Principles

- **Single FastAPI backend** — no microservices.
- **Models loaded once** at startup, cached as singletons.
- **Incremental indexing** — MD5 fingerprints prevent re-indexing.
- **Graceful degradation** — Qdrant/Ollama down → HTTP 503 with actionable message;
  per-page OCR failures never abort a document.
- **Explainability** — every answer carries `[filename, page]` citations and the
  reranked chunks are surfaced in the UI.
