import io


def _upload_book(client, headers, title="Test Book"):
    r = client.post("/api/books", headers=headers,
                    files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
                    data={"title": title, "author": "Author"})
    assert r.status_code == 201, r.text
    return r.json()


def test_book_crud(client, auth_headers):
    book = _upload_book(client, auth_headers)
    assert book["title"] == "Test Book"
    assert book["status"] in ("uploaded", "processing", "ready")

    lst = client.get("/api/books", headers=auth_headers).json()
    assert any(b["id"] == book["id"] for b in lst)

    # another user cannot see it
    client.post("/api/auth/register", json={"email": "x@y.com", "password": "password123"})
    other_token = client.cookies.get("bl_session")
    r = client.get("/api/books", headers={"Authorization": f"Bearer {other_token}"})
    assert all(b["id"] != book["id"] for b in r.json())

    # restore original user's session (cookie was overwritten by second register)
    client.cookies.set("bl_session", auth_headers["Authorization"][7:])
    assert client.delete(f"/api/books/{book['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/books/{book['id']}", headers=auth_headers).status_code == 404


def test_shelves_and_progress(client, auth_headers):
    book = _upload_book(client, auth_headers)
    shelf = client.post("/api/shelves", headers=auth_headers,
                        json={"name": "Favorites"}).json()
    r = client.post(f"/api/shelves/{shelf['id']}/books", headers=auth_headers,
                    json={"book_id": book["id"]})
    assert r.status_code == 200

    r = client.put(f"/api/books/{book['id']}/progress", headers=auth_headers,
                   json={"last_page": 10, "percent": 25.0})
    assert r.status_code == 200
    got = client.get(f"/api/books/{book['id']}/progress", headers=auth_headers).json()
    assert got["last_page"] == 10
