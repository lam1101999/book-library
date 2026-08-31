"""Summarization: map-reduce over chapter text via an OpenAI-compatible API."""
import httpx

from .config import settings


def _chat(messages: list[dict], max_tokens: int = 900) -> str:
    r = httpx.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={"model": settings.llm_model, "messages": messages,
              "max_tokens": max_tokens, "temperature": 0.3},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _extract_pages(reader, start: int, end: int, max_chars: int) -> str:
    parts, total = [], 0
    for pno in range(start, min(end + 1, len(reader.pages))):
        try:
            t = reader.pages[pno].extract_text() or ""
        except Exception:  # noqa: BLE001
            t = ""
        if total + len(t) > max_chars:
            parts.append(t[: max(0, max_chars - total)])
            break
        parts.append(t)
        total += len(t)
    return "\n".join(parts)


def summarize_chunk(text: str, book_title: str, chapter_title: str) -> str:
    return _chat([
        {"role": "system", "content": "You summarize book chapters accurately and concisely."},
        {"role": "user", "content":
            f"Book: {book_title}\nChapter: {chapter_title}\n\n"
            f"Summarize the following excerpt. Capture key arguments, facts and conclusions.\n\n{text}"},
    ])


def summarize_chapter(reader, chapter: dict, book_title: str) -> tuple[str, str]:
    """Map-reduce: chunk -> chunk summaries -> final. Returns (tldr, detailed)."""
    text = _extract_pages(reader, chapter["start_page"], chapter["end_page"],
                          max_chars=settings.chunk_chars * 4)
    if len(text) <= settings.chunk_chars:
        detailed = _chat([
            {"role": "system", "content": "You summarize book chapters accurately and concisely."},
            {"role": "user", "content":
                f"Book: {book_title}\nChapter: {chapter['title']}\n\n"
                f"Write a detailed summary (200-350 words) of:\n\n{text}"},
        ], max_tokens=700)
    else:
        chunks = [text[i:i + settings.chunk_chars]
                  for i in range(0, len(text), settings.chunk_chars)][:6]
        partials = [summarize_chunk(c, book_title, chapter["title"]) for c in chunks]
        detailed = _chat([
            {"role": "user", "content":
                f"Book: {book_title}\nChapter: {chapter['title']}\n\n"
                "These are summaries of consecutive chunks of one chapter. "
                "Merge them into one detailed, non-redundant summary (200-350 words):\n\n"
                + "\n\n---\n\n".join(partials)},
        ], max_tokens=700)
    tldr = _chat([
        {"role": "user", "content": f"Condense to exactly 2 sentences:\n\n{detailed}"},
    ], max_tokens=120)
    return tldr, detailed
