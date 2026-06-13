#!/bin/bash
set -e

echo "===== Biology RAG Chatbot - Demo Mode ====="

# Step 1: Check prerequisites (hard requirements)
command -v ollama >/dev/null 2>&1 || { echo "Ollama is required. Install from https://ollama.ai"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.10+ is required."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 18+ is required."; exit 1; }
# Optional: only needed to OCR scanned PDFs.
command -v tesseract >/dev/null 2>&1 || echo "[warn] Tesseract not found - OCR for scanned PDFs disabled (sample PDFs need no OCR)."

OLLAMA_MODEL="${OLLAMA_MODEL:-mistral:7b}"
# Embedded Qdrant by default — no Docker server required.
export QDRANT_MODE="${QDRANT_MODE:-local}"

# Step 2: Qdrant
echo "[1/7] Using embedded Qdrant (no Docker) -> backend/qdrant_storage"

# Step 3: Start Ollama and pull model
echo "[2/7] Starting Ollama LLM server..."
ollama serve &
sleep 2
echo "Pulling ${OLLAMA_MODEL} model (this may take a while on first run)..."
ollama pull "${OLLAMA_MODEL}"

# Step 4: Install Python dependencies
echo "[3/7] Installing Python dependencies..."
cd backend
python3 -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt --quiet

# Generate sample PDFs if none present.
if [ -z "$(ls -A sample_pdfs/*.pdf 2>/dev/null)" ]; then
  echo "Generating sample PDFs..."
  python3 scripts/generate_sample_pdfs.py
fi

# Step 5: Ingest sample PDFs
echo "[4/7] Ingesting sample PDFs..."
python3 -c "
from app.ingestion.extractor import PDFExtractor
from app.ingestion.ocr import OCRProcessor
from app.ingestion.cleaner import TextCleaner
from app.ingestion.chunker import TextChunker
from app.ingestion.fingerprint import DocumentFingerprintManager, compute_md5
from app.embeddings.embedder import BiologyEmbedder
from app.vectordb.qdrant_client import QdrantManager
import os, glob

pdfs = glob.glob('./sample_pdfs/*.pdf')
print(f'Found {len(pdfs)} sample PDFs')

embedder = BiologyEmbedder()
qdrant = QdrantManager(); qdrant.ensure_collection()
fingerprints = DocumentFingerprintManager()
extractor, ocr, cleaner, chunker = PDFExtractor(), OCRProcessor(), TextCleaner(), TextChunker()

for pdf_path in pdfs:
    if fingerprints.is_indexed(pdf_path):
        print(f'  -> Skipping (already indexed): {os.path.basename(pdf_path)}'); continue
    print(f'Processing: {os.path.basename(pdf_path)}')
    pages = extractor.extract(pdf_path)
    scanned = [p.page_number for p in pages if p.is_scanned]
    if scanned:
        ocr_texts = ocr.process_scanned_pages(pdf_path, scanned)
        for p in pages:
            if p.is_scanned: p.text = ocr_texts.get(p.page_number, '')
    for p in pages:
        p.text = cleaner.clean(p.text, p.page_number, p.source_file)
    pdf_id = compute_md5(pdf_path)
    chunks = chunker.chunk_pages(pages, os.path.basename(pdf_path), pdf_id)
    embeddings = embedder.embed_chunks(chunks)
    count = qdrant.upsert_chunks(chunks, embeddings)
    fingerprints.mark_indexed(pdf_path, {'chunk_count': count})
    print(f'  -> Indexed {count} chunks')

print('Ingestion complete!')
"

# Step 6: Start FastAPI backend
# NOTE: no --reload in embedded Qdrant mode (the reloader would open a second
# handle on the on-disk DB and hit a file lock).
echo "[5/7] Starting FastAPI backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 3
echo "Backend running at http://localhost:8000"

# Step 7: Start Next.js frontend
echo "[6/7] Starting Next.js frontend..."
cd ../frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
sleep 3

echo ""
echo "===== Demo Ready! ====="
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Health:   http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all services"

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; ollama stop 2>/dev/null; echo 'Services stopped.'" EXIT

wait
