# Corpus directory (`backend/pdfs/`)

PDFs are **not committed** to the repository — they are large (the full corpus is
~2.2 GB and individual files exceed GitHub's 100 MB limit) and are excluded via
`.gitignore`. This folder holds the biology knowledge base that gets ingested
into the vector database.

## How to populate this folder

Drop any biology PDFs here, then index them either by:

- clicking **"Ingest server directory"** in the web UI (Ingestion panel), or
- running the ingestion script directly:
  ```bash
  cd backend
  python scripts/ingest_samples.py "./pdfs/*.pdf"
  ```

Ingestion is idempotent — already-indexed files are skipped via MD5 fingerprints
(`backend/fingerprints/indexed_docs.json`), so re-running is safe.

## Demo without your own PDFs

If you just want to try the app, generate three small synthetic biology PDFs:
```bash
cd backend
python scripts/generate_sample_pdfs.py     # writes to ./sample_pdfs/
python scripts/ingest_samples.py            # ingests ./sample_pdfs/*.pdf
```

## Corpus used during development

The system was built and validated against these 10 books (~10,900 chunks indexed):

| File | Notes |
|---|---|
| Biology-2e.pdf | OpenStax — native text |
| Biology-AP-Courses.pdf | OpenStax — native text |
| Concepts-Biology.pdf | OpenStax — native text |
| anatomy-and-physiology-2e.pdf | OpenStax — native text |
| microbiology.pdf | OpenStax — native text |
| Introduction-Behavioral-Neuroscience.pdf | native text |
| organic-chemistry.pdf | native text |
| neet book.pdf | native text |
| 11th combined NCERT SMASHER_2.0.pdf | scanned — requires Tesseract OCR |
| NCERT SMASHER 2.0 [12th Combine].pdf | scanned — requires Tesseract OCR |

OpenStax titles are free/openly licensed and downloadable from
<https://openstax.org/subjects/science>.

> **Scanned PDFs:** the two NCERT files are image-based. They only index fully when
> Tesseract OCR 5.x is installed and on `PATH` (or `TESSERACT_CMD` is set in the
> backend config). Without it, native-text books still index normally.
