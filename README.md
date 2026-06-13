# Biology RAG Chatbot

A **100% local, free, open-source** Retrieval-Augmented Generation (RAG) chatbot
over biology textbooks. Ingests PDFs (native text + OCR for scanned pages),
embeds and indexes them in a vector database, retrieves and reranks the most
relevant passages, and generates grounded answers with a local LLM — **every
answer cites the source PDF filename and page number**.

No paid APIs. No cloud dependencies. Runs entirely on your machine.

---

## What This Is

- **Corpus:** any biology PDFs (OpenStax Biology 2e, Anatomy & Physiology,
  Microbiology, etc.). 10+ large books are supported; 3 small synthetic
  samples ship for the demo.
- **Pipeline:** PDF → extract/OCR → clean → chunk → embed → Qdrant → retrieve →
  cross-encoder rerank → Ollama LLM → answer + citations.
- **Target latency:** 2–5 seconds end-to-end.

## Architecture

```
                         ┌──────────────────────────────────────────────┐
   PDFs ──► Extract ──►  │ OCR (scanned only) ─► Clean ─► Chunk (750 tok) │
                         └───────────────┬──────────────────────────────┘
                                         ▼
                              Embed (BGE-small, 384-d)
                                         ▼
                              Qdrant (HNSW, cosine)
                                         ▲
   Query ─► Embed ─► ANN search (top-10) ─┘ ─► Cross-encoder rerank (top-4)
                                                          ▼
                                            Ollama LLM (mistral:7b)
                                                          ▼
                                          Answer + [filename, page] citations
```

```
Next.js frontend (:3000)  ──HTTP──►  FastAPI backend (:8000)
                                         ├── Qdrant   (:6333, Docker)
                                         └── Ollama   (:11434, local binary)
```

## Prerequisites

**Required**
- **Python 3.10–3.13** (3.10/3.11 give the smoothest install of the pinned versions).
- **Node.js 18+**
- **Ollama** — https://ollama.ai

**Optional**
- **Docker** — only needed if you run Qdrant as a server (`QDRANT_MODE=server`).
  By default the app runs Qdrant **embedded/in-process** (`QDRANT_MODE=local`),
  so Docker is not required.
- **Tesseract OCR 5.x** — only needed to OCR *scanned* PDFs. Native-text PDFs
  (including the bundled samples) need no OCR; the app degrades gracefully if
  Tesseract is absent.

**Hardware:** 8 GB RAM minimum, 16 GB recommended.

## Quick Start

### Windows (PowerShell)

```powershell
# From the biology-rag/ directory
powershell -ExecutionPolicy Bypass -File .\start_demo.ps1
```

### macOS / Linux

```bash
cd biology-rag
chmod +x start_demo.sh
./start_demo.sh
```

Then open **http://localhost:3000**, and either use the pre-ingested samples or
upload your own PDFs from the Ingestion panel.

> The default LLM is `mistral:7b`. Override with `OLLAMA_MODEL=llama3:8b` in the
> environment before launching.

## Manual Setup

### Qdrant
Embedded mode (default) needs no setup — the app persists vectors to
`backend/qdrant_storage/`. To use a server instead:
```bash
docker-compose up -d qdrant      # http://localhost:6333
# then set QDRANT_MODE=server in backend/.env
```

### Ollama
```bash
ollama serve
ollama pull mistral:7b           # or: ollama pull llama3:8b
```

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1   |   Unix: source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_sample_pdfs.py    # creates 3 demo PDFs
python scripts/ingest_samples.py          # seed the vector DB
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
cp .env.local.example .env.local          # optional; defaults to :8000
npm install
npm run dev                                # http://localhost:3000
```

## Adding Your Biology PDFs

1. Drop PDF files into `backend/pdfs/` (server-side) **or** upload them via the
   Ingestion panel in the UI.
2. Server-directory ingest: `POST /ingest` with `{ "pdf_dir": "./pdfs" }`.
3. Re-running ingestion is safe — already-indexed files are skipped via MD5
   fingerprints (`backend/fingerprints/indexed_docs.json`).

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat` | `{query, top_k?, top_k_rerank?}` → answer, citations, chunks, latency |
| POST | `/ingest` | Multipart `files[]` **or** JSON `{pdf_dir}` → per-file results |
| POST | `/ingest/status` | Indexed documents + total chunk count |
| GET  | `/health` | Aggregate component health |
| GET  | `/health/vector-db` | Qdrant status + point count |
| GET  | `/health/llm` | Ollama status + model |
| GET  | `/health/ocr` | Tesseract version |
| GET  | `/health/embedding` | Embedding model + dimensions |
| GET  | `/metrics` | Query count, avg/p95 latency, error rate |

Interactive docs: **http://localhost:8000/docs**

### Example
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the function of mitochondria?"}'
```

## Configuration

All settings have defaults (see `backend/.env.example`). Override via environment
variables or a `backend/.env` file. Key ones: `QDRANT_HOST/PORT`, `OLLAMA_MODEL`,
`CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K_RETRIEVAL`, `TOP_K_RERANK`.

Frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

## Troubleshooting

- **Qdrant not starting:** ensure Docker is running; `docker-compose up -d qdrant`;
  check `http://localhost:6333/dashboard`.
- **Ollama model not found:** `ollama pull mistral:7b`. Confirm `ollama serve` is up.
- **OCR not working:** install Tesseract 5.x and ensure `tesseract` is on PATH
  (`tesseract --version`). On Windows, the UB-Mannheim build is recommended.
- **Slow responses:** the LLM dominates latency. Use a smaller/quantized model,
  reduce `TOP_K_RERANK`, or ensure the model is warm.
- **Python 3.12/3.13 install errors:** the pinned `numpy==1.26.4` /
  `tiktoken==0.7.0` may lack wheels for very new Python. Use Python 3.10/3.11,
  or relax those pins (`pip install numpy tiktoken` unpinned) for local dev.
- **First query is slow:** embedding + reranker models download on first run and
  are cached afterwards.

## Vercel Deployment (frontend only)

1. Deploy `frontend/` to Vercel (free tier).
2. Set `NEXT_PUBLIC_API_URL` to your backend URL (e.g. an ngrok tunnel or a
   self-hosted VM).
3. The backend (FastAPI + Qdrant + Ollama) continues to run locally or on a
   free-tier Linux VM. `next.config.js` already sets `output: 'standalone'`.

## Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

The embedder tests require the real embedding model; they skip automatically if
it cannot be loaded offline. All other suites run fully mocked.

---

See [TECH_STACK.md](TECH_STACK.md) for the full dependency rationale and
[PROJECT_INTERVIEW_GUIDE.md](PROJECT_INTERVIEW_GUIDE.md) for a deep technical walkthrough.
