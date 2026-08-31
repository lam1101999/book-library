"""API routes: books CRUD + upload, chapters, reading progress."""
import secrets
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Book, Chapter, ReadingProgress, get_db
from .tasks import process_book, summarize_book_chapter

router = APIRouter()

ALLOWED = {".pdf"}
MAX_SIZE = 100 * 1024 * 1024  # 100 MB


# ---- schemas ----
class BookOut(BaseModel):
    id: int
    title: str
    author: str
    num_pages: int
    status: str
    error: str

    class Config:
        from_attributes = True


class ChapterOut(BaseModel):
    id: int
    number: int | None
    title: str
    start_page: int
    end_page: int
    source: str
    summary: str
    tldr: str
    summarized: int

    class Config:
        from_attributes = True


class ChapterEdit(BaseModel):
    title: str | None = None
    start_page: int | None = None
    end_page: int | None = None


# ---- books ----
@router.get("/api/books", response_model=list[BookOut])
def list_books(db: Session = Depends(get_db)):
    return db.scalars(select(Book).order_by(Book.created_at.desc())).all()


@router.post("/api/books", response_model=BookOut, status_code=201)
async def upload_book(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = None,
    author: str = "",
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "Only PDF files are supported")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "File too large (max 100 MB)")

    stored = f"{secrets.token_hex(8)}{ext}"
    (settings.storage_dir / stored).write_bytes(data)

    book = Book(
        title=(title or Path(file.filename).stem)[:500],
        author=author[:500],
        filename=stored,
        status="uploaded",
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    background.add_task(process_book, book.id)
    return book


@router.get("/api/books/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


@router.delete("/api/books/{book_id}", status_code=204)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    try:
        (settings.storage_dir / book.filename).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(book)
    db.commit()


@router.get("/api/books/{book_id}/file")
def book_file(book_id: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    path = settings.storage_dir / book.filename
    if not path.exists():
        raise HTTPException(404, "File missing")
    return FileResponse(path, media_type="application/pdf", filename=book.filename)


# ---- chapters ----
@router.get("/api/books/{book_id}/chapters", response_model=list[ChapterOut])
def list_chapters(book_id: int, db: Session = Depends(get_db)):
    if not db.get(Book, book_id):
        raise HTTPException(404, "Book not found")
    return db.scalars(select(Chapter).where(Chapter.book_id == book_id)
                      .order_by(Chapter.start_page)).all()


@router.post("/api/books/{book_id}/chapters/{chapter_id}/summarize", status_code=202)
def summarize_chapter(book_id: int, chapter_id: int, background: BackgroundTasks,
                      db: Session = Depends(get_db)):
    chapter = db.get(Chapter, chapter_id)
    if not chapter or chapter.book_id != book_id:
        raise HTTPException(404, "Chapter not found")
    if not settings.llm_api_key:
        raise HTTPException(503, "LLM API key not configured (set LIBRARY_LLM_API_KEY)")
    background.add_task(summarize_book_chapter, book_id, chapter_id)
    return {"detail": "summarization started"}


@router.patch("/api/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def edit_chapter(book_id: int, chapter_id: int, body: ChapterEdit,
                 db: Session = Depends(get_db)):
    chapter = db.get(Chapter, chapter_id)
    if not chapter or chapter.book_id != book_id:
        raise HTTPException(404, "Chapter not found")
    if body.title is not None:
        chapter.title = body.title[:500]
    if body.start_page is not None:
        chapter.start_page = max(0, body.start_page)
    if body.end_page is not None:
        chapter.end_page = max(chapter.start_page, body.end_page)
    db.commit()
    return chapter


# ---- reading progress ----
class ProgressIn(BaseModel):
    last_page: int


@router.put("/api/books/{book_id}/progress")
def set_progress(book_id: int, body: ProgressIn, db: Session = Depends(get_db)):
    if not db.get(Book, book_id):
        raise HTTPException(404, "Book not found")
    book = db.get(Book, book_id)
    percent = min(100.0, body.last_page / max(1, book.num_pages) * 100)
    prog = db.scalars(select(ReadingProgress).where(ReadingProgress.book_id == book_id)).first()
    if not prog:
        prog = ReadingProgress(book_id=book_id)
        db.add(prog)
    prog.last_page = max(0, body.last_page)
    prog.percent = percent
    db.commit()
    return {"last_page": prog.last_page, "percent": round(prog.percent, 1)}


@router.get("/api/books/{book_id}/progress")
def get_progress(book_id: int, db: Session = Depends(get_db)):
    prog = db.scalars(select(ReadingProgress).where(ReadingProgress.book_id == book_id)).first()
    return {"last_page": prog.last_page if prog else 0,
            "percent": round(prog.percent, 1) if prog else 0.0}
