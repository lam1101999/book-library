"""Background processing: extract chapters after upload, optionally summarize."""
import logging

from pypdf import PdfReader
from sqlalchemy.orm import Session

from . import chapter_detector, summarizer
from .config import settings
from .models import Book, Chapter, SessionLocal

log = logging.getLogger("library.tasks")


def process_book(book_id: int) -> None:
    """Detect chapters (PDF outline only) + render cover; background thread."""
    db: Session = SessionLocal()
    try:
        book = db.get(Book, book_id)
        if not book:
            return
        book.status = "processing"
        db.commit()

        path = settings.storage_dir / book.filename
        reader = PdfReader(str(path))

        chapters, method = chapter_detector.build_chapters(reader)
        book.num_pages = len(reader.pages)
        # render page-1 cover thumbnail (non-fatal if it fails)
        from . import covers
        covers.render_cover(path, settings.storage_dir / f"cover_{book.id}.png")
        # replace any existing auto-detected chapters (manual ones would only
        # exist after this first pass anyway)
        book.chapters.clear()
        db.flush()
        for i, ch in enumerate(chapters):
            db.add(Chapter(
                book_id=book.id,
                number=ch.get("number", i + 1),
                title=ch["title"],
                start_page=ch["start_page"],
                end_page=ch["end_page"],
                source=ch.get("source", method),
            ))
        book.status = "ready"
        book.error = ""
        db.commit()
        log.info("book %s: %d chapters via %s", book_id, len(chapters), method)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        book = db.get(Book, book_id)
        if book:
            book.status = "error"
            book.error = str(e)[:1000]
            db.commit()
        log.exception("processing failed for book %s", book_id)
    finally:
        db.close()


def summarize_book_chapter(book_id: int, chapter_id: int) -> None:
    """Summarize one chapter (map-reduce). Also runs as a background task."""
    db: Session = SessionLocal()
    try:
        book = db.get(Book, book_id)
        chapter = db.get(Chapter, chapter_id)
        if not book or not chapter or not settings.llm_api_key:
            return
        doc = PdfReader(str(settings.storage_dir / book.filename))
        tldr, detailed = summarizer.summarize_chapter(
            doc, {"title": chapter.title, "start_page": chapter.start_page,
                  "end_page": chapter.end_page},
            book.title,
        )
        chapter.tldr = tldr
        chapter.summary = detailed
        chapter.summarized = 1
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        log.exception("summarization failed for chapter %s: %s", chapter_id, e)
    finally:
        db.close()
