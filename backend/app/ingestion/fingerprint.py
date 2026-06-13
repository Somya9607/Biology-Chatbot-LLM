"""Document fingerprinting to prevent re-indexing already-indexed PDFs.

Each PDF is hashed (MD5 of its raw bytes) and recorded in a JSON registry.
Re-running ingestion on a file whose hash is already present is a no-op.

Registry format::

    {
      "<md5_hash>": {
        "filename": "biology2e.pdf",
        "indexed_at": "2026-06-13T10:00:00+00:00",
        "chunk_count": 1234
      }
    }
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)


def compute_md5(pdf_path: str) -> str:
    """Return the MD5 hex digest of a file's raw bytes (streamed)."""
    md5 = hashlib.md5()
    with open(pdf_path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            md5.update(block)
    return md5.hexdigest()


class DocumentFingerprintManager:
    """Thread-safe registry of indexed-document fingerprints.

    Reads and writes are guarded by a process-level lock and performed as
    atomic load-modify-save cycles to avoid corrupting the registry file.
    """

    def __init__(self, fingerprint_file: str | None = None) -> None:
        self._path = Path(fingerprint_file or settings.FINGERPRINT_FILE)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({})

    # --- internal helpers ---------------------------------------------------
    def _read(self) -> Dict[str, Any]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            log.warning("fingerprint.read_failed", error=str(exc))
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        # Atomic write via temp file + replace.
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)

    # --- public API ---------------------------------------------------------
    def is_indexed(self, pdf_path: str) -> bool:
        """Return True if the file's MD5 is already present in the registry."""
        digest = compute_md5(pdf_path)
        with self._lock:
            return digest in self._read()

    def mark_indexed(self, pdf_path: str, metadata: Dict[str, Any]) -> None:
        """Record a file as indexed, storing filename, timestamp, chunk count."""
        digest = compute_md5(pdf_path)
        with self._lock:
            data = self._read()
            data[digest] = {
                "filename": os.path.basename(pdf_path),
                "indexed_at": datetime.now(timezone.utc).isoformat(),
                "chunk_count": int(metadata.get("chunk_count", 0)),
            }
            self._write(data)
        log.info(
            "fingerprint.marked",
            filename=os.path.basename(pdf_path),
            md5=digest,
            chunk_count=metadata.get("chunk_count", 0),
        )

    def get_all_indexed(self) -> Dict[str, Any]:
        """Return the full registry mapping md5 -> metadata."""
        with self._lock:
            return self._read()
