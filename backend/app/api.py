"""API routes: books CRUD + upload, chapters, shelves, reading progress (per user)."""
import secrets
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth_api import current_user
from .config import settings
from .models import (Book, Chapter, ReadingProgress, Shelf, ShelfBook,
                     User, get_db)
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


class ShelfOut(BaseModel):
    id: int
    name: str
    book_ids: list[int]

    class Config:
        from_attributes = True


class ShelfCreate(BaseModel):
    name: str


def _get_own_book(db: Session, user: User, book_id: int) -> Book:
    book = db.get(Book, book_id)
    if not book or book.user_id != user.id:
        raise HTTPException(404, "Book not found")
    return book


# ---- books ----
@router.get("/api/books", response_model=list[BookOut])
def list_books(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Book).where(Book.user_id == user.id)
                      .order_by(Book.created_at.desc())).all()


@router.post("/api/books", response_model=BookOut, status_code=201)
async def upload_book(background: BackgroundTasks, file: UploadFile = File(...),
                      title: str | None = Form(None), author: str = Form(""),
                      user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "Only PDF files are supported")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "File too large (max 100 MB)")

    stored = f"{user.id}/{secrets.token_hex(8)}{ext}"
    dest = settings.storage_dir / stored
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    book = Book(user_id=user.id, title=(title or Path(file.filename).stem)[:500],
                author=author[:500], filename=stored, status="uploaded")
    db.add(book)
    db.commit()
    db.refresh(book)
    background.add_task(process_book, book.id)
    return book


@router.get("/api/books/{book_id}", response_model=BookOut)
def get_book(book_id: int, user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    return _get_own_book(db, user, book_id)


@router.delete("/api/books/{book_id}", status_code=204)
def delete_book(book_id: int, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    book = _get_own_book(db, user, book_id)
    try:
        (settings.storage_dir / book.filename).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(book)
    db.commit()


@router.get("/api/books/{book_id}/file")
def book_file(book_id: int, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    book = _get_own_book(db, user, book_id)
    path = settings.storage_dir / book.filename
    if not path.exists():
        raise HTTPException(404, "File missing")
    return FileResponse(path, media_type="application/pdf", filename=book.filename)


@router.get("/api/books/{book_id}/cover")
def book_cover(book_id: int, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    _get_own_book(db, user, book_id)
    path = settings.storage_dir / f"cover_{book_id}.png"
    if not path.exists():
        raise HTTPException(404, "Cover not available")
    return FileResponse(path, media_type="image/png")


# ---- manual outline (DB-backed; PDF file only modified on explicit write-back) ----

class ChapterCreate(BaseModel):
    title: str
    start_page: int
    end_page: int | None = None


@router.post("/api/books/{book_id}/chapters", response_model=ChapterOut, status_code=201)
def create_chapter(book_id: int, body: ChapterCreate,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    _get_own_book(db, user, book_id)
    book = db.get(Book, book_id)
    n_pages = book.num_pages or 0
    if not (0 <= body.start_page < max(n_pages, body.start_page + 1)):
        raise HTTPException(400, "start_page out of range")
    ch = Chapter(
        book_id=book_id, title=body.title.strip()[:500],
        start_page=body.start_page,
        end_page=body.end_page if body.end_page is not None else body.start_page,
        source="manual",
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.delete("/api/books/{book_id}/chapters/{chapter_id}", status_code=204)
def delete_chapter(book_id: int, chapter_id: int,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    _get_own_book(db, user, book_id)
    ch = db.get(Chapter, chapter_id)
    if not ch or ch.book_id != book_id:
        raise HTTPException(404, "Chapter not found")
    db.delete(ch)
    db.commit()


@router.post("/api/books/{book_id}/outline/save-to-pdf")
def save_outline_to_pdf(book_id: int, user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
    """Write the current DB outline into the PDF's embedded bookmarks.

    Writes to a temp file then atomically replaces the original; the old
    outline tree is cleared first so no stale bookmarks remain.
    """
    _get_own_book(db, user, book_id)
    book = db.get(Book, book_id)
    chapters = db.scalars(select(Chapter).where(Chapter.book_id == book_id)
                          .order_by(Chapter.start_page)).all()
    src = settings.storage_dir / book.filename
    if not src.exists():
        raise HTTPException(404, "File missing")

    import io
    import os
    import tempfile
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (ArrayObject, DictionaryObject, NameObject,
                               NumberObject, TextStringObject)

    reader = PdfReader(str(src))
    writer = PdfWriter()
    writer.append(reader)  # clones pages
    # replace the outline tree with a fresh one built from the DB
    outlines = DictionaryObject()
    outlines_ref = writer._add_object(outlines)
    root = writer._root_object
    root[NameObject("/Outlines")] = outlines_ref
    outlines[NameObject("/Type")] = NameObject("/Outlines")
    outlines[NameObject("/Count")] = NumberObject(len(chapters))
    last_ref = None
    for ch in chapters:
        ref = writer._add_object(DictionaryObject())
        item = writer.get_object(ref)
        item[NameObject("/Title")] = TextStringObject(ch.title)
        item[NameObject("/Parent")] = outlines_ref
        item[NameObject("/Dest")] = ArrayObject(
            [writer.pages[ch.start_page].indirect_reference, NameObject("/Fit")])
        if last_ref is None:
            outlines[NameObject("/First")] = ref
        else:
            writer.get_object(last_ref)[NameObject("/Next")] = ref
            item[NameObject("/Prev")] = last_ref
        outlines[NameObject("/Last")] = ref
        if ch.source == "manual":
            item[NameObject("/F")] = NumberObject(1)  # bold in viewers
        last_ref = ref

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=str(settings.storage_dir))
    with os.fdopen(fd, "wb") as f:
        f.write(buf.read())
    os.replace(tmp_name, src)
    return {"detail": f"{len(chapters)} bookmarks written to PDF"}


# ---- chapters ----
@router.get("/api/books/{book_id}/chapters", response_model=list[ChapterOut])
def list_chapters(book_id: int, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    _get_own_book(db, user, book_id)
    return db.scalars(select(Chapter).where(Chapter.book_id == book_id)
                      .order_by(Chapter.start_page)).all()


@router.post("/api/books/{book_id}/chapters/{chapter_id}/summarize", status_code=202)
def summarize_chapter(book_id: int, chapter_id: int, background: BackgroundTasks,
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    _get_own_book(db, user, book_id)
    chapter = db.get(Chapter, chapter_id)
    if not chapter or chapter.book_id != book_id:
        raise HTTPException(404, "Chapter not found")
    if not settings.llm_api_key:
        raise HTTPException(503, "LLM API key not configured (set LIBRARY_LLM_API_KEY)")
    background.add_task(summarize_book_chapter, book_id, chapter_id)
    return {"detail": "summarization started"}


@router.patch("/api/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def edit_chapter(book_id: int, chapter_id: int, body: ChapterEdit,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    _get_own_book(db, user, book_id)
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


# ---- shelves ----
@router.get("/api/shelves", response_model=list[ShelfOut])
def list_shelves(user: User = Depends(current_user), db: Session = Depends(get_db)):
    shelves = db.scalars(select(Shelf).where(Shelf.user_id == user.id)
                         .order_by(Shelf.created_at)).all()
    out = []
    for s in shelves:
        ids = [item.book_id for item in s.items]
        out.append(ShelfOut(id=s.id, name=s.name, book_ids=ids))
    return out


@router.post("/api/shelves", response_model=ShelfOut, status_code=201)
def create_shelf(body: ShelfCreate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    shelf = Shelf(user_id=user.id, name=body.name.strip()[:200])
    db.add(shelf)
    db.commit()
    db.refresh(shelf)
    return ShelfOut(id=shelf.id, name=shelf.name, book_ids=[])


@router.delete("/api/shelves/{shelf_id}", status_code=204)
def delete_shelf(shelf_id: int, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(404, "Shelf not found")
    db.delete(shelf)
    db.commit()


class ShelfAddIn(BaseModel):
    book_id: int


@router.post("/api/shelves/{shelf_id}/books", response_model=ShelfOut)
def add_to_shelf(shelf_id: int, body: ShelfAddIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(404, "Shelf not found")
    book = db.get(Book, body.book_id)
    if not book or book.user_id != user.id:
        raise HTTPException(404, "Book not found")
    exists = db.scalars(select(ShelfBook).where(
        ShelfBook.shelf_id == shelf_id, ShelfBook.book_id == body.book_id)).first()
    if not exists:
        db.add(ShelfBook(shelf_id=shelf_id, book_id=body.book_id))
        db.commit()
    return ShelfOut(id=shelf.id, name=shelf.name,
                    book_ids=[i.book_id for i in shelf.items])


@router.delete("/api/shelves/{shelf_id}/books/{book_id}", status_code=204)
def remove_from_shelf(shelf_id: int, book_id: int, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    shelf = db.get(Shelf, shelf_id)
    if not shelf or shelf.user_id != user.id:
        raise HTTPException(404, "Shelf not found")
    item = db.scalars(select(ShelfBook).where(
        ShelfBook.shelf_id == shelf_id, ShelfBook.book_id == book_id)).first()
    if item:
        db.delete(item)
        db.commit()


# ---- reading progress (synced per user) ----
class ProgressIn(BaseModel):
    last_page: int


@router.put("/api/books/{book_id}/progress")
def set_progress(book_id: int, body: ProgressIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    book = _get_own_book(db, user, book_id)
    percent = min(100.0, body.last_page / max(1, book.num_pages) * 100)
    prog = db.scalars(select(ReadingProgress).where(
        ReadingProgress.user_id == user.id,
        ReadingProgress.book_id == book_id)).first()
    if not prog:
        prog = ReadingProgress(user_id=user.id, book_id=book_id)
        db.add(prog)
    prog.last_page = max(0, body.last_page)
    prog.percent = percent
    db.commit()
    return {"last_page": prog.last_page, "percent": round(prog.percent, 1)}


@router.get("/api/books/{book_id}/progress")
def get_progress(book_id: int, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    prog = db.scalars(select(ReadingProgress).where(
        ReadingProgress.user_id == user.id,
        ReadingProgress.book_id == book_id)).first()
    return {"last_page": prog.last_page if prog else 0,
            "percent": round(prog.percent, 1) if prog else 0.0}


@router.get("/api/progress")
def all_progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Reading progress for all user's books — used by the library grid."""
    rows = db.scalars(select(ReadingProgress).where(
        ReadingProgress.user_id == user.id)).all()
    return {str(r.book_id): {"last_page": r.last_page, "percent": round(r.percent, 1)}
            for r in rows}
