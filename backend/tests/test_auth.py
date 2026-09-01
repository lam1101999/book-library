def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_login_me(client):
    r = client.post("/api/auth/register", json={
        "email": "a@b.com", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.com"

    # duplicate email -> 409
    r2 = client.post("/api/auth/register", json={
        "email": "a@b.com", "password": "password123"})
    assert r2.status_code == 409

    # short password -> 400
    r3 = client.post("/api/auth/register", json={
        "email": "c@b.com", "password": "short"})
    assert r3.status_code == 400

    r4 = client.post("/api/auth/login", json={
        "email": "a@b.com", "password": "password123"})
    assert r4.status_code == 200

    r5 = client.post("/api/auth/login", json={
        "email": "a@b.com", "password": "wrongpassword"})
    assert r5.status_code == 401

    # /me via cookie session
    r6 = client.get("/api/auth/me")
    assert r6.status_code == 200
    assert r6.json()["email"] == "a@b.com"


def test_me_unauthenticated(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_default_shelves_created(client, auth_headers):
    shelves = client.get("/api/shelves", headers=auth_headers).json()
    assert {s["name"] for s in shelves} == {"Reading", "Want to read", "Finished"}
