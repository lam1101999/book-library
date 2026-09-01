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
