# Project Interview Guide — Biology RAG Chatbot

## 1. Project Overview (30-second pitch)

> "I built a fully local, open-source Retrieval-Augmented Generation chatbot over
> biology textbooks. It ingests PDFs — including scanned ones via OCR — chunks and
> embeds them with a BGE sentence-transformer, indexes them in Qdrant with an HNSW
> ANN index, then at query time retrieves the top candidates, reranks them with a
> cross-encoder, and generates a grounded answer with a local Mistral model through
> Ollama. Every answer cites the exact PDF and page number, and the whole pipeline
> runs in 2–5 seconds with zero paid services."

## 2. Architecture Deep Dive

### RAG Pipeline
1. **Ingestion** — PyMuPDF extracts native text; pages with <50 chars are flagged
   as scanned and OCR'd with Tesseract (per-page) or OCRmyPDF (full-doc). Text is
   normalized (NFC, control-char strip, de-hyphenation, page-number removal),
   chunked to 750 tokens with 150-token overlap (tiktoken), and embedded.
2. **Indexing** — 384-dim vectors are upserted into a Qdrant collection with a
   cosine HNSW index (m=16, ef_construct=200) and a payload carrying
   `{text, source_file, page_number, chunk_index, pdf_id}`.
3. **Retrieval** — the query is embedded (with the BGE query-instruction prefix)
   and ANN-searched for the top-10 candidates.
4. **Reranking** — a cross-encoder jointly scores each (query, passage) pair and
   keeps the top-4.
5. **Generation** — the reranked passages become a labelled context block; a strict
   system prompt instructs the LLM to answer only from context and cite sources.

### Why Each Component
- **BGE-small** — strong MTEB retrieval scores at 384 dims (cheap to store/search),
  33M params, runs on CPU.
- **Qdrant** — production-grade OSS vector DB with HNSW, payload filtering, and an
  easy Docker deployment.
- **Cross-encoder reranker** — recovers precision lost by approximate bi-encoder
  search at a small latency cost.
- **Ollama** — local LLM serving, no API key, swappable models.

### Trade-offs
- Bi-encoder ANN (fast, approximate) + cross-encoder rerank (slow, precise) over a
  small candidate set — best of both.
- Page-level chunking keeps citations precise at the cost of occasionally splitting
  context across a page boundary.
- 750/150 token chunking balances recall (smaller chunks) vs. context coherence
  (larger chunks).

## 3. Key Technical Concepts (Q&A)

**Q: What is RAG and why use it instead of fine-tuning?**
A: RAG retrieves relevant documents at inference time and conditions the LLM on
them. Versus fine-tuning, it needs no training, updates instantly when documents
change, grounds answers in citable sources (reducing hallucination), and is far
cheaper. Fine-tuning bakes knowledge into weights and is better for style/format,
not for a frequently-changing knowledge base.

**Q: Why BAAI/bge-small-en-v1.5 for embeddings?**
A: It's free, fast, CPU-friendly (33M params, 384 dims) and scores highly on MTEB
retrieval. Smaller dimensions mean cheaper storage and faster ANN search. BGE
models use an asymmetric scheme — a query-side instruction prefix — which we apply
only to queries, not documents.

**Q: What is HNSW and why use it over brute-force search?**
A: Hierarchical Navigable Small World is a graph-based ANN index. Brute force is
O(N) per query; HNSW gives near-logarithmic search by navigating a multi-layer
proximity graph. `m` controls graph connectivity and `ef_construct` the build-time
search breadth — higher values trade indexing time/memory for recall.

**Q: How does the cross-encoder reranker improve results?**
A: A bi-encoder embeds query and document independently, so similarity is
approximate. A cross-encoder feeds the (query, passage) pair through the model
together with full cross-attention, producing a far more accurate relevance score.
It's too slow to run over the whole corpus, so we only rerank the top-10
candidates.

**Q: How do you handle scanned PDFs?**
A: During extraction, any page whose native text is under 50 characters is flagged
as scanned. Only those pages are OCR'd — per-page with pytesseract on a 2x-rendered
image, or via `ocrmypdf --skip-text` when most of the document is scanned. Pages
that already have text are never OCR'd.

**Q: How do you prevent hallucination?**
A: (1) A strict system prompt instructing answers strictly from context with an
explicit "I don't have enough information" fallback; (2) low-temperature, grounded
generation over reranked, relevant passages; (3) mandatory citations so claims are
traceable; (4) surfacing the retrieved chunks in the UI for verification.

**Q: How does chunking affect retrieval quality?**
A: Chunks too large dilute the embedding and hurt precision; too small lose context
and fragment ideas. 750 tokens with ~20% overlap keeps each chunk topically focused
while the overlap preserves continuity across boundaries so answers near a chunk
edge aren't cut off.

**Q: What is the 2–5 second latency budget and how do you meet it?**
A: Approximate breakdown: query embedding ~50 ms, Qdrant ANN ~20 ms, cross-encoder
rerank ~200 ms, LLM generation ~2–4 s. The LLM dominates, so we use a small 7B
quantized model, keep it warm, and limit reranking to a handful of passages.
Per-stage latency is measured and returned in every response.

**Q: How would you scale this to millions of documents?**
A: Qdrant scales to millions of vectors and supports sharding/replication and
quantization (scalar/product) to cut memory. Ingestion can be parallelized and run
as a batch/stream job. Add metadata filtering to narrow search, a caching layer for
hot queries, and horizontally scale stateless backend replicas behind a load
balancer. Move the LLM to a GPU server or a managed OSS endpoint.

**Q: What evaluation metrics do you track?**
A: Retrieval quality — Recall@k and MRR against a labelled query/passage set;
serving — latency p95 (tracked live) and error rate; answer quality —
hallucination/groundedness rate via spot checks. The `/metrics` endpoint exposes
query count, avg/p95 latency and error rate in real time.

## 4. Challenges Faced & How Solved
- **Scanned PDF handling** — selective per-page OCR vs. full-doc OCR based on the
  scanned-page ratio, so we never waste time OCR-ing pages that already have text.
- **Chunking boundaries** — sentence-aware greedy packing with token-budgeted
  overlap to avoid mid-sentence cuts.
- **Latency** — small models, top-K limits, models loaded once at startup, warm
  LLM; per-stage timing to find regressions.
- **Idempotent ingestion** — MD5 fingerprints in a JSON registry skip already-indexed
  files so re-running never duplicates vectors.
- **Mixed multipart/JSON ingest endpoint** — branch on `Content-Type` from the raw
  request rather than fighting FastAPI's body binding.

## 5. What You Would Improve With More Time
- Semantic chunking (spaCy sentence segmentation, layout-aware splitting).
- Hybrid search (BM25 sparse + dense fusion) for keyword-heavy queries.
- A biology-domain fine-tuned embedding model.
- Streaming token responses to the UI.
- A user-feedback loop (thumbs up/down) feeding evaluation and future RLHF.
- A proper eval harness computing Recall@k / MRR on a curated question set.

## 6. Demo Script
1. Show the **health dashboard** — Vector DB / LLM / OCR / Embedding all green.
2. Show the **Ingestion panel** — X documents, Y chunks indexed.
3. Ask: *"What is the function of mitochondria?"*
4. Show the **answer with citations** (`[filename, page]`).
5. Expand **Retrieved Chunks** — vector vs. rerank scores per passage.
6. Show the **latency breakdown** chips (retrieval / rerank / generation / total).
7. Ask a **cross-document** question to show multi-source synthesis.

## 7. Non-functional Requirements Checklist
- **Open/Free:** BGE + Qdrant + Ollama + Tesseract — all free/OSS. ✓
- **Scalability:** Qdrant handles millions of vectors; incremental indexing. ✓
- **Latency:** 2–5 s target via HNSW + small reranker + quantized LLM. ✓
- **Explainability:** every answer includes PDF filename + page number. ✓
- **Reproducibility:** deterministic chunking (fixed tokens + tiktoken),
  precomputed/persisted embeddings, seeded language detection. ✓
