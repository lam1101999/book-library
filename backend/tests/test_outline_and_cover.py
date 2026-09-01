"""Cover endpoint + manual outline CRUD + save-outline-to-PDF write-back."""
import io

from pypdf import PdfReader


def _make_pdf(pages: int = 3) -> bytes:
    """Build a tiny in-memory PDF with the given page count."""
    from pypdf import PdfWriter
    w = PdfWriter()
    for i in range(pages):
        w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _upload_pdf(client, headers, pages=3, title="T"):
    data = _make_pdf(pages)
    r = client.post("/api/books", headers=headers,
                    files={"file": ("t.pdf", io.BytesIO(data), "application/pdf")},
                    data={"title": title})
    assert r.status_code == 201, r.text
    return r.json()


def test_cover_404_then_ok(client, auth_headers):
    book = _upload_pdf(client, auth_headers)
    # cover renders in background; poll briefly
    import time
    ok = False
    for _ in range(20):
        time.sleep(0.2)
        r = client.get(f"/api/books/{book['id']}/cover", headers=auth_headers)
        if r.status_code == 200:
            ok = True
            assert r.headers["content-type"].startswith("image/png")
            break
    assert ok, "cover never appeared"


def test_manual_outline_crud_and_save_to_pdf(client, auth_headers):
    book = _upload_pdf(client, auth_headers, pages=5)
    bid = book["id"]
    import time
    for _ in range(20):
        time.sleep(0.2)
        if client.get(f"/api/books/{bid}", headers=auth_headers).json()["status"] == "ready":
            break

    # no embedded outline in this generated PDF -> no chapters
    assert client.get(f"/api/books/{bid}/chapters", headers=auth_headers).json() == []

    # create manual entries
    r1 = client.post(f"/api/books/{bid}/chapters", headers=auth_headers,
                     json={"title": "Intro", "start_page": 0})
    assert r1.status_code == 201, r1.text
    r2 = client.post(f"/api/books/{bid}/chapters", headers=auth_headers,
                     json={"title": "Body", "start_page": 2, "end_page": 4})
    assert r2.status_code == 201
    chs = client.get(f"/api/books/{bid}/chapters", headers=auth_headers).json()
    assert [c["title"] for c in chs] == ["Intro", "Body"]
    assert all(c["source"] == "manual" for c in chs)

    # write back into the PDF
    r = client.post(f"/api/books/{bid}/outline/save-to-pdf", headers=auth_headers)
    assert r.status_code == 200, r.text

    # download the PDF and verify embedded bookmarks
    f = client.get(f"/api/books/{bid}/file", headers=auth_headers)
    assert f.status_code == 200
    reader = PdfReader(io.BytesIO(f.content))
    assert reader.outline, "PDF should now have an outline"
    titles = [o.title for o in reader.outline]
    assert titles == ["Intro", "Body"]

    # outline detection now finds them from the file itself
    from app.chapter_detector import build_chapters
    chapters, method = build_chapters(reader)
    assert method == "toc"
    assert len(chapters) == 2

    # delete one
    r = client.delete(f"/api/books/{bid}/chapters/{chs[0]['id']}", headers=auth_headers)
    assert r.status_code == 204
    remaining = client.get(f"/api/books/{bid}/chapters", headers=auth_headers).json()
    assert [c["title"] for c in remaining] == ["Body"]


def test_create_chapter_validation(client, auth_headers):
    book = _upload_pdf(client, auth_headers, pages=2)
    bid = book["id"]
    r = client.post(f"/api/books/{bid}/chapters", headers=auth_headers,
                    json={"title": "Neg", "start_page": -1})
    assert r.status_code == 400


def test_other_user_cannot_touch_outline(client, auth_headers):
    book = _upload_pdf(client, auth_headers)
    bid = book["id"]
    client.post("/api/auth/register", json={"email": "x@y.com", "password": "password123"})
    r = client.post(f"/api/books/{bid}/outline/save-to-pdf",
                    headers={"Authorization": f"Bearer {client.cookies.get('bl_session')}"})
    assert r.status_code == 404
