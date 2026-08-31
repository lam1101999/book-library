"""Vercel serverless entrypoint wrapping the FastAPI app."""
import os

# Serverless: ephemeral filesystem -> storage under /tmp
os.environ.setdefault("LIBRARY_DATABASE_URL", "sqlite:////tmp/library.db")
os.environ.setdefault("LIBRARY_STORAGE_DIR", "/tmp/files")

from app.main import app  # noqa: E402

handler = app
