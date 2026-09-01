"""Shared fixtures: throwaway Postgres DB + TestClient per test session."""
import os
import uuid

import pytest

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:55432/postgres")

# unique schema per run so parallel/repeat runs never collide
_TEST_SCHEMA = f"test_{uuid.uuid4().hex[:12]}"
os.environ["LIBRARY_DATABASE_URL"] = TEST_DB_URL
os.environ["LIBRARY_STORAGE_DIR"] = os.environ.get("TEST_STORAGE_DIR", "/tmp/bl-test-files")
os.makedirs(os.environ["LIBRARY_STORAGE_DIR"], exist_ok=True)

from sqlalchemy import event, text  # noqa: E402  (env must be set before importing app)
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.models import engine  # noqa: E402


@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, record):
    cur = dbapi_conn.cursor()
    cur.execute(f"SET search_path TO {_TEST_SCHEMA}, public")
    cur.close()


@pytest.fixture(scope="module", autouse=True)
def _test_schema():
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{_TEST_SCHEMA}"'))
        # create_all(checkfirst=True) finds tables in `public` (inspector ignores
        # our search_path) and skips creating them in the test schema -> drop them
        conn.execute(text(
            'DO $$ DECLARE r RECORD; BEGIN'
            ' FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = \'public\''
            ' LOOP EXECUTE \'DROP TABLE IF EXISTS public.\' || r.tablename || \' CASCADE\';'
            ' END LOOP; END $$;'))
    yield
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{_TEST_SCHEMA}" CASCADE'))
    # pooled connections keep the stale search_path; force fresh connections
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(_test_schema):
    yield
    with engine.begin() as conn:
        # schema-scoped truncate of all tables init_db created (no IF EXISTS in PG)
        conn.execute(text(
            f'DO $$ DECLARE r RECORD; BEGIN'
            f' FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = \'{_TEST_SCHEMA}\''
            f' LOOP EXECUTE \'TRUNCATE TABLE "{_TEST_SCHEMA}".\' || r.tablename || \' CASCADE\';'
            f' END LOOP; END $$;'))


@pytest.fixture()
def client():
    # fresh client per test; init_db runs on startup.
    # https base_url: session cookie is Secure, httpx won't send it over http.
    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    """Register a user and return Bearer headers."""
    r = client.post("/api/auth/register", json={
        "email": "test@example.com", "password": "password123", "name": "Test"})
    assert r.status_code == 200, r.text
    token = r.cookies.get("bl_session")
    return {"Authorization": f"Bearer {token}"}
