"""Application configuration via pydantic-settings.

All runtime configuration is loaded from environment variables (optionally a
``.env`` file) with sensible local-first defaults. Nothing is hardcoded
elsewhere in the codebase: every tunable path or parameter lives here.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe application settings.

    Values are read from the process environment (case-insensitive) and fall
    back to the defaults defined below. A local ``.env`` file is also honoured.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Vector database (Qdrant) -------------------------------------------
    # QDRANT_MODE="local" runs Qdrant embedded/on-disk in-process (no Docker,
    # persists to QDRANT_PATH). QDRANT_MODE="server" connects to a running
    # Qdrant server at QDRANT_HOST:QDRANT_PORT (e.g. via docker-compose).
    QDRANT_MODE: str = "local"
    QDRANT_PATH: str = "./qdrant_storage"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "biology_rag"

    # --- OCR -----------------------------------------------------------------
    # Absolute path to the Tesseract binary. Leave empty to rely on PATH.
    # On Windows the UB-Mannheim build installs to:
    #   C:\Program Files\Tesseract-OCR\tesseract.exe
    TESSERACT_CMD: str = ""

    # --- Models --------------------------------------------------------------
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- LLM (Ollama) --------------------------------------------------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # "mistral:latest" is the Mistral 7B model; "mistral:7b" is an equivalent tag.
    OLLAMA_MODEL: str = "mistral:latest"

    # --- Chunking ------------------------------------------------------------
    CHUNK_SIZE: int = 750          # tokens per chunk
    CHUNK_OVERLAP: int = 150       # token overlap between chunks (~20%)

    # --- Retrieval / reranking ----------------------------------------------
    TOP_K_RETRIEVAL: int = 10
    TOP_K_RERANK: int = 4

    # --- Paths ---------------------------------------------------------------
    PDF_DIR: str = "./pdfs"
    FINGERPRINT_FILE: str = "./fingerprints/indexed_docs.json"
    LOG_DIR: str = "./logs"

    # --- Performance ---------------------------------------------------------
    MAX_LATENCY_TARGET_MS: int = 5000


settings = Settings()
"""Module-level singleton imported throughout the application."""
