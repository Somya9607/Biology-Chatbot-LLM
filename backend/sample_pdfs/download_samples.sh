#!/bin/bash
# Generate (or download) biology sample PDFs for demo mode.
#
# NOTE: The OpenStax book pages are served as HTML, not direct PDF downloads,
# so this script generates small self-contained sample PDFs locally instead.
# For a full-scale corpus, download the official OpenStax PDFs from
# https://openstax.org/subjects/science and drop them into ../pdfs/.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Generating synthetic biology sample PDFs..."
python3 "$SCRIPT_DIR/../scripts/generate_sample_pdfs.py"
echo "Done. Add your own PDFs to backend/sample_pdfs/ or backend/pdfs/ for full ingestion."
