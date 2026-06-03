"""
utils/helpers.py — shared helpers for all routers
"""

import os
import uuid
import tempfile
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import HTTPException, UploadFile

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 50 * 1024 * 1024   # 50 MB

ALLOWED_MIME = {
    "pdf":   {"application/pdf"},
    "image": {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/gif"},
    "video": {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska"},
    "audio": {"audio/mpeg", "audio/wav", "audio/ogg", "audio/flac", "audio/aac"},
    "word":  {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    },
}


# ── Temp file helpers ─────────────────────────────────────────────────────────

async def save_upload(upload: UploadFile, suffix: str = "") -> Path:
    """Save an UploadFile to a temp file and return its Path."""
    data = await upload.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE // (1024*1024)} MB)")
    tmp = Path(tempfile.mktemp(suffix=suffix or Path(upload.filename or "file").suffix))
    tmp.write_bytes(data)
    return tmp


def temp_path(suffix: str = "") -> Path:
    """Return a fresh temp-file path (not yet created)."""
    return Path(tempfile.mktemp(suffix=suffix))


def cleanup(*paths: Path):
    """Delete temp files silently."""
    for p in paths:
        try:
            if p and Path(p).exists():
                os.unlink(p)
        except Exception:
            pass


@asynccontextmanager
async def tmp_scope(*paths: Path):
    """Context manager that deletes temp files on exit."""
    try:
        yield
    finally:
        cleanup(*paths)


# ── MIME validation ───────────────────────────────────────────────────────────

def require_mime(upload: UploadFile, category: str):
    allowed = ALLOWED_MIME.get(category, set())
    ct = (upload.content_type or "").split(";")[0].strip().lower()
    if ct not in allowed:
        raise HTTPException(
            415,
            f"Unsupported file type '{ct}'. Allowed: {', '.join(sorted(allowed))}",
        )


# ── Generic error wrapper ─────────────────────────────────────────────────────

def tool_error(msg: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=msg)
