# Book Library

Personal PDF library with **AI chapter detection and summarization**. Multi-user, local-first: everything runs in Docker on your machine.

- **Frontend:** Vite + React + TypeScript, PDF reader via `react-pdf` (pdf.js), served by nginx
- **Backend:** FastAPI + SQLAlchemy (PostgreSQL 16), background chapter processing
- **Database:** Postgres (docker compose service, data persists in a named volume)
- **Summarization:** any OpenAI-compatible LLM endpoint (default: OpenRouter GLM Flash)

## Features

- Multi-user accounts (email/password + Google OAuth ready), JWT session cookies
- Upload PDFs; chapters are auto-detected from the PDF outline (bookmarks) or
  by text-pattern scanning (supports "Chapter N" and Vietnamese "Chương N")
- Reader view with chapter sidebar, zoom, scroll-position page tracking
- Per-chapter AI summaries: 2-sentence TL;DR + detailed summary (map-reduce for long chapters)
- Reading progress saved automatically; shelves (Reading / Want to read / Finished)
- Chapter metadata editable (fix wrong detections without re-uploading)

## Quick start (Docker)

```bash
docker compose up -d
```

App: **http://localhost:8080** — Postgres is healthy-gated before the backend starts; tables are created automatically on first boot. Data persists across restarts in the `pgdata` volume (uploads in `uploads`).

Useful commands:

```bash
docker compose ps                      # service status
docker compose logs -f backend         # backend logs
docker compose exec db psql -U library -d library
docker compose down                    # stop (data kept)
docker compose down -v                 # stop and wipe data
```

### Run the test suite (in Docker)

```bash
docker compose --profile test run --rm test
```

## Local development (no Docker)

```bash
# Postgres (any instance works; or use the compose db)
# export LIBRARY_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/library

cd backend
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
export LIBRARY_DATABASE_URL="postgresql+psycopg://postgres@localhost:55432/postgres"
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
npm test             # Vitest suite
```

Backend tests (uses a throwaway schema; needs a reachable Postgres):

```bash
cd backend && python -m pytest -v
```

## E2E tests (Playwright — real browser against the running app)

```bash
cd frontend
npm install
npx playwright install chromium    # one-time browser download
# start the app first (docker compose up -d, or the dev stack), then:
BASE_URL=http://localhost:8080 npm run e2e
```

9 journeys: auth (register/login/errors), library (upload → cover renders → delete), reader (pages render, outline add/edit/delete, save-into-PDF). Set `BASE_URL` to wherever the app runs; tests create their own users.

## Configuration (env vars, prefix `LIBRARY_`)

| Var | Default (compose) | Purpose |
|---|---|---|
| `LIBRARY_DATABASE_URL` | `postgresql+psycopg://library:library@db:5432/library` | Postgres connection |
| `LIBRARY_STORAGE_DIR` | `/app/data/files` | Uploaded PDF storage |
| `LIBRARY_LLM_API_KEY` | — | OpenAI-compatible API key for summarization |
| `LIBRARY_LLM_MODEL` | `z-ai/glm-5.3-flash` | Summarization model |

## How chapter detection works

1. **Tier 1 — PDF outline.** If the PDF has bookmarks (`/Outlines`), top-level entries become chapters.
2. **Tier 2 — text patterns.** Regex scan of the top of each page for `Chapter \d+`, `Chương \d+`, `Part N`, roman numerals.
3. **Fallback.** No chapters found → whole book is one "chapter"; still summarizable, boundaries editable via the API.

## API

Interactive docs at http://localhost:8080/api/docs (or :8000/docs in dev). Highlights:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` / `/api/auth/login` | Account + session |
| POST | `/api/books` | Upload PDF (multipart: `file`, `title`, `author`) |
| GET | `/api/books/{id}/chapters` | Detected chapters |
| POST | `/api/books/{id}/chapters/{cid}/summarize` | Start background summarization |
| PUT | `/api/books/{id}/progress` | Save reading position |

## Notes

- Summaries are cached in the DB; only re-run when you ask.
- Chapter summarization runs in a background task — the UI polls until done.
- For long chapters (>~12k chars) the summarizer uses map-reduce over chunks.
