# Biology RAG Chatbot - Demo Mode (Windows PowerShell)
# Usage:  powershell -ExecutionPolicy Bypass -File .\start_demo.ps1
$ErrorActionPreference = "Stop"

Write-Host "===== Biology RAG Chatbot - Demo Mode (Windows) ====="

function Assert-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "Missing prerequisite: $name. $hint" -ForegroundColor Red
        exit 1
    }
}

function Test-OptionalCommand($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "Optional tool not found: $name. $hint" -ForegroundColor Yellow
    }
}

# Step 1: Prerequisites (hard requirements)
Assert-Command ollama "Install from https://ollama.ai"
Assert-Command python "Install Python 3.10+ (3.10 or 3.11 recommended)."
Assert-Command node   "Install Node.js 18+."
# Optional: only needed to OCR scanned PDFs. Sample PDFs need no OCR.
Test-OptionalCommand tesseract "OCR for scanned PDFs is disabled until Tesseract 5.x is on PATH (UB-Mannheim build)."

$OllamaModel = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "mistral:latest" }
$root = $PSScriptRoot

# Embedded Qdrant — no Docker server required.
$env:QDRANT_MODE = "local"

# Step 2: Qdrant runs embedded/in-process (on-disk at backend\qdrant_storage)
Write-Host "[1/7] Using embedded Qdrant (no Docker) -> backend\qdrant_storage"

# Step 3: Start Ollama + pull model
Write-Host "[2/7] Starting Ollama LLM server..."
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "Pulling $OllamaModel (first run may take a while)..."
ollama pull $OllamaModel

# Step 4: Python deps
Write-Host "[3/7] Installing Python dependencies..."
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet

# Generate sample PDFs if none present
if (-not (Get-ChildItem "sample_pdfs\*.pdf" -ErrorAction SilentlyContinue)) {
    Write-Host "Generating sample PDFs..."
    & ".\.venv\Scripts\python.exe" "scripts\generate_sample_pdfs.py"
}

# Step 5: Ingest sample PDFs
Write-Host "[4/7] Ingesting sample PDFs..."
& ".\.venv\Scripts\python.exe" "scripts\ingest_samples.py"

# Step 6: Start backend
Write-Host "[5/7] Starting FastAPI backend..."
$backend = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" `
    -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "Backend running at http://localhost:8000"

# Step 7: Start frontend
Write-Host "[6/7] Starting Next.js frontend..."
Set-Location "$root\frontend"
npm install --silent
$frontend = Start-Process -FilePath "npm" -ArgumentList "run","dev" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "===== Demo Ready! ====="
Write-Host "Frontend: http://localhost:3000"
Write-Host "Backend:  http://localhost:8000"
Write-Host "API Docs: http://localhost:8000/docs"
Write-Host "Health:   http://localhost:8000/health"
Write-Host ""
Write-Host "Press Enter to stop all services..."
[void][System.Console]::ReadLine()

# Cleanup
if ($backend -and -not $backend.HasExited)  { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
Write-Host "Services stopped."
