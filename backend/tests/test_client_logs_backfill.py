"""Client error-log endpoint + startup cover backfill."""
import io
import time


def test_client_log_accepts_error(client):
    r = client.post("/api/client-logs", json={
        "level": "error",
        "message": "PDF load failed: Setting up fake worker failed",
        "source": "pdf.mjs:1",
        "url": "http://localhost:8080/book/1",
        "user_agent": "test-agent",
        "stack": "Error: fake worker\n  at ...",
    })
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_client_log_accepts_warn(client):
    r = client.post("/api/client-logs", json={
        "level": "warn", "message": "slow render",
    })
    assert r.status_code == 200


def test_backfill_covers_renders_missing(client, auth_headers):
    import io as _io
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=300, height=400)
    buf = io.BytesIO()
    w.write(buf)
    r = client.post("/api/books", headers=auth_headers,
                    files={"file": ("t.pdf", buf, "application/pdf")},
                    data={"title": "Backfill"})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]

    # wait for processing
    for _ in range(20):
        time.sleep(0.2)
        if client.get(f"/api/books/{bid}", headers=auth_headers).json()["status"] == "ready":
            break

    # simulate a book with no cover: delete the rendered cover file, then backfill
    from app.config import settings
    from pathlib import Path
    cover = Path(settings.storage_dir) / f"cover_{bid}.png"
    cover.unlink(missing_ok=True)
    assert not cover.exists()

    r = client.post("/api/admin/backfill-covers")
    assert r.status_code == 200
    assert r.json()["rendered"] >= 1

    # now the cover endpoint serves it
    r = client.get(f"/api/books/{bid}/cover", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
