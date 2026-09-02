"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as books_router
from .auth_api import router as auth_router
from .client_logs import router as client_logs_router
from .config import settings
from .models import SessionLocal, init_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Book Library", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # same-origin in prod via rewrites; loose for local dev
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router)
app.include_router(books_router)
app.include_router(client_logs_router)


@app.on_event("startup")
def startup():
    init_db()
    # one-time cover backfill for books uploaded before covers existed
    from sqlalchemy import select
    from . import covers
    from .models import Book
    db = SessionLocal()
    try:
        books = db.execute(select(Book.id, Book.filename)).all()
        n = covers.backfill_covers(settings.storage_dir, books)
        if n:
            logging.getLogger("library.covers").info("startup backfill: %d covers rendered", n)
    except Exception:
        logging.getLogger("library.covers").exception("startup cover backfill failed")
    finally:
        db.close()


@app.post("/api/admin/backfill-covers")
def backfill_covers_endpoint():
    """Manual trigger: render covers for any books missing one."""
    from sqlalchemy import select
    from . import covers
    from .models import Book
    db = SessionLocal()
    try:
        books = db.execute(select(Book.id, Book.filename)).all()
        n = covers.backfill_covers(settings.storage_dir, books)
        return {"rendered": n, "total_books": len(books)}
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
