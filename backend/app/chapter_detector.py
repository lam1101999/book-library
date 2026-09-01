"""Chapter detection: PDF TOC first, then text-pattern regex fallback (pypdf)."""
import re

from pypdf import PdfReader

# Title-case-ish heading followed by chapter-ish keyword; supports EN + VI
CHAPTER_PATTERNS = [
    re.compile(r"^\s*(chapter|chap\.?)\s+(\d+|[IVXLC]+)\b[\s.:\-–—]*(.{0,120})$", re.I | re.M),
    re.compile(r"^\s*(chương)\s+(\d+)\b[\s.:\-–—]*(.{0,120})$", re.I | re.M),
    re.compile(r"^\s*(part|phần)\s+(\d+|[IVXLC]+)\b[\s.:\-–—]*(.{0,120})$", re.I | re.M),
]

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _roman_to_int(s: str) -> int | None:
    s = s.upper()
    if not re.fullmatch(r"[IVXLC]+", s):
        return None
    vals = [ROMAN[c] for c in s]
    total = 0
    for i, v in enumerate(vals):
        if i + 1 < len(vals) and v < vals[i + 1]:
            total -= v
        else:
            total += v
    return total


def _walk_outline(reader, items, depth=1, out=None):
    """Flatten pypdf outline (nested lists) into (level, title, page_idx)."""
    if out is None:
        out = []
    for it in items:
        if isinstance(it, list):
            _walk_outline(reader, it, depth + 1, out)
        else:
            page_idx = None
            try:
                page_idx = it.page.get_index()
            except Exception:  # noqa: BLE001  (pypdf 5: /Dest arrays need reader helper)
                try:
                    page_idx = reader.get_destination_page_number(it)
                except Exception:  # noqa: BLE001
                    page_idx = None
            out.append((depth, str(it.title), page_idx))
    return out


def detect_from_toc(reader: PdfReader) -> list[dict] | None:
    """Tier 1: embedded PDF outline/bookmarks."""
    try:
        outline = reader.outline
    except Exception:  # noqa: BLE001
        return None
    if not outline:
        return None
    flat = _walk_outline(reader, outline)
    chapters = [
        {"title": t.strip()[:500], "start_page": p, "source": "toc"}
        for d, t, p in flat
        if d == 1 and t.strip() and p is not None and p >= 0
    ]
    return chapters if len(chapters) >= 2 else None


def detect_from_text(reader: PdfReader, max_pages: int = 400) -> list[dict]:
    """Tier 2: regex over page text. Returns chapters with page spans."""
    hits: list[dict] = []
    n = min(len(reader.pages), max_pages)
    for pno in range(n):
        try:
            text = reader.pages[pno].extract_text() or ""
        except Exception:  # noqa: BLE001
            continue
        if not text:
            continue
        # only look at the top 40% of the page text (headings live there)
        head = "\n".join(text.splitlines()[: max(4, int(len(text.splitlines()) * 0.4))])
        for pat in CHAPTER_PATTERNS:
            m = pat.search(head)
            if m:
                num = m.group(2)
                number = int(num) if num.isdigit() else _roman_to_int(num)
                label = (m.group(3) or "").strip(" .:-–—")
                title = f"{m.group(1).title()} {num}" + (f": {label}" if label else "")
                hits.append({"title": title[:500], "start_page": pno, "number": number,
                             "source": "regex"})
                break  # one hit per page
    if len(hits) < 2:
        return hits
    # drop hits on the same page as a previous hit (keep first)
    dedup, seen = [], set()
    for h in hits:
        if h["start_page"] not in seen:
            dedup.append(h)
            seen.add(h["start_page"])
    return dedup


def build_chapters(reader: PdfReader) -> tuple[list[dict], str]:
    """Returns (chapters_with_spans, method). Chapters get end_page filled in.

    Outline policy: only embedded PDF bookmarks (/Outlines) are used. If the
    PDF has none, return no chapters — the user creates them manually in the
    reader (stored in DB with source='manual'), the PDF file is never modified.
    """
    toc = detect_from_toc(reader)
    method = "toc" if toc else "none"
    if not toc:
        return [], method
    n_pages = len(reader.pages)
    for i, ch in enumerate(toc):
        ch["end_page"] = (toc[i + 1]["start_page"] - 1) if i + 1 < len(toc) else n_pages - 1
    return toc, method
