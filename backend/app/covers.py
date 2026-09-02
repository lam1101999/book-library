"""Cover thumbnails: render page 1 of a PDF to PNG via pypdfium2."""
import logging

import pypdfium2 as pdfium

log = logging.getLogger("library.covers")


def render_cover(pdf_path, out_path, width=320) -> bool:
    """Render page 1 to PNG. Returns True on success."""
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        try:
            page = pdf[0]
            scale = width / page.get_width()
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            img.save(out_path, "PNG")
            return True
        finally:
            pdf.close()
    except Exception:  # noqa: BLE001
        log.exception("cover render failed for %s", pdf_path)
        return False


def backfill_covers(storage_dir, books: list) -> int:
    """Render covers for books missing one. `books` = (id, filename) tuples.
    Returns count rendered. Logs each failure to server logs."""
    from pathlib import Path

    done = 0
    for book_id, filename in books:
        out = Path(storage_dir) / f"cover_{book_id}.png"
        if out.exists():
            continue
        src = Path(storage_dir) / filename
        if not src.exists():
            log.warning("cover backfill: source missing for book %s (%s)", book_id, filename)
            continue
        if render_cover(src, out):
            done += 1
            log.info("cover backfill: rendered cover for book %s", book_id)
        else:
            log.error("cover backfill: render failed for book %s", book_id)
    return done
