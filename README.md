<<<<<<< HEAD
# book-library

Personal PDF library with AI chapter detection and summarization.

See the feature/mvp-scaffold branch / PR for the MVP implementation.
=======
# Book Library

Personal PDF library with **AI chapter detection and summarization**.

- **Frontend:** Vite + React + TypeScript, PDF reader via `react-pdf` (pdf.js)
- **Backend:** FastAPI + SQLAlchemy (SQLite), PDF parsing via PyMuPDF
- **Summarization:** any OpenAI-compatible LLM endpoint (default: OpenRouter GLM Flash)

## Features

- Upload PDFs; chapters are auto-detected from the PDF outline (bookmarks) or
  by text-pattern scanning (supports "Chapter N" and Vietnamese "Chương N")
- Reader view with chapter sidebar, zoom, scroll-position page tracking
- Per-chapter AI summaries: 2-sentence TL;DR + detailed summary (map-reduce for long chapters)
- Reading progress saved automatically
- Chapter metadata editable (fix wrong detections without re-uploading)

## Quick start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in LIBRARY_LLM_API_KEY (OpenRouter key works)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

## How chapter detection works

1. **Tier 1 — PDF outline.** If the PDF has bookmarks (`/Outlines`), top-level
   entries become chapters. Most publisher PDFs have these.
2. **Tier 2 — text patterns.** Regex scan of the top of each page for
   `Chapter \d+`, `Chương \d+`, `Part N`, roman numerals.
3. **Fallback.** No chapters found → whole book is one "chapter"; you can
   still summarize it, and edit chapter boundaries via the API.

## API

Interactive docs at http://localhost:8000/docs. Highlights:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/books` | Upload PDF (multipart, `file` field) |
| GET | `/api/books` | List books |
| GET | `/api/books/{id}/chapters` | Detected chapters |
| POST | `/api/books/{id}/chapters/{cid}/summarize` | Start background summarization |
| PATCH | `/api/books/{id}/chapters/{cid}` | Fix title / page span |
| PUT | `/api/books/{id}/progress` | Save reading position |

## Notes

- Summaries are cached in the DB; only re-run when you ask.
- Chapter summarization runs in a background task — the UI polls until done.
- For long chapters (>~12k chars) the summarizer uses map-reduce over chunks.
>>>>>>> 9ae4147 (feat: MVP — FastAPI backend (book CRUD, chapter detection, summarization) + Vite React frontend (library, PDF reader))
