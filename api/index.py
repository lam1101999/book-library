"""Vercel serverless entrypoint wrapping the FastAPI app."""
import os
import sys
from pathlib import Path

# Serverless: ephemeral filesystem -> storage under /tmp
os.environ.setdefault("LIBRARY_DATABASE_URL", "sqlite:////tmp/library.db")
os.environ.setdefault("LIBRARY_STORAGE_DIR", "/tmp/files")

_API_DIR = Path(__file__).resolve().parent
for p in (str(_API_DIR), str(_API_DIR / "app")):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.main import app  # noqa: E402

handler = app
