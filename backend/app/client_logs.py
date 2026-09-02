"""Client-side error logging: browser errors POSTed here land in server logs.

Catches everything a user hits (JS exceptions, unhandled rejections, PDF worker
failures, console.error) so `docker compose logs backend` shows them — the
morning bug-scan greps these.
"""
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

log = logging.getLogger("library.client")
router = APIRouter(prefix="/api/client-logs", tags=["client-logs"])


class ClientLog(BaseModel):
    level: str = "error"          # error | warn | info
    message: str
    source: str = ""              # file:line of the error, if known
    stack: str = ""               # stack trace, if any
    url: str = ""                 # page URL where it happened
    user_agent: str = ""


@router.post("")
async def client_log(entry: ClientLog, request: Request):
    line = f"[{entry.level}] {entry.message}"
    if entry.source:
        line += f" @ {entry.source}"
    if entry.url:
        line += f" | page: {entry.url}"
    if entry.stack:
        line += f"\n  stack: {entry.stack[:2000]}"
    if entry.user_agent:
        line += f"\n  ua: {entry.user_agent[:200]}"
    if entry.level == "warn":
        log.warning(line)
    else:
        log.error(line)
    return {"ok": True}
