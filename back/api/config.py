from __future__ import annotations

import os
from pathlib import Path


BACK_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACK_DIR.parent

DATABASE_URL = os.getenv(
    "ANTIPLAG_DATABASE_URL",
    "postgresql+psycopg://antiplag:antiplag@127.0.0.1:55432/antiplag",
)
REDIS_URL = os.getenv("ANTIPLAG_REDIS_URL", "redis://127.0.0.1:6379/0")
QUEUE_NAME = os.getenv("ANTIPLAG_QUEUE_NAME", "antiplag-checks")
UPLOADS_DIR = Path(os.getenv("ANTIPLAG_UPLOADS_DIR", PROJECT_DIR / "storage" / "uploads"))

ALLOWED_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".zip",
}

MAX_UPLOAD_BYTES = int(os.getenv("ANTIPLAG_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
MAX_AI_CANDIDATES = int(os.getenv("ANTIPLAG_MAX_AI_CANDIDATES", "5"))
CLASSIC_SCORE_WEIGHT = float(os.getenv("ANTIPLAG_CLASSIC_SCORE_WEIGHT", "0.65"))
AI_SCORE_WEIGHT = float(os.getenv("ANTIPLAG_AI_SCORE_WEIGHT", "0.35"))
