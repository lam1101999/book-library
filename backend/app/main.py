"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as books_router
from .auth_api import router as auth_router
from .models import init_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Book Library", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # same-origin in prod via rewrites; loose for local dev
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router)
app.include_router(books_router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
