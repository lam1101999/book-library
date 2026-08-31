"""Auth API: register, login, Google OAuth, current-user dependency."""
import datetime
import secrets
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, decode_token,
                   google_auth_url, hash_password, make_token, verify_password)
from .models import Shelf, User, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "bl_session"
STATE_COOKIE = "bl_oauth_state"


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: resolves user from session cookie or Authorization bearer."""
    token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    user_id = decode_token(token) if token else None
    if not user_id:
        raise HTTPException(401, "Not signed in")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _set_session(response: Response, user: User):
    token = make_token(user.id)
    response.set_cookie(COOKIE_NAME, token, max_age=30 * 86400,
                        httponly=True, samesite="lax", secure=True)


@router.post("/register")
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    existing = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if existing:
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email.lower(), name=body.name[:200],
                password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    # default shelves
    for name in ("Reading", "Want to read", "Finished"):
        db.add(Shelf(user_id=user.id, name=name))
    db.commit()
    _set_session(response, user)
    return {"id": user.id, "email": user.email, "name": user.name}


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    _set_session(response, user)
    return {"id": user.id, "email": user.email, "name": user.name}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}


# ---- Google OAuth ----
@router.get("/google")
def google_start():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google login not configured")
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(google_auth_url(state), status_code=302)
    resp.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True,
                    samesite="lax", secure=True)
    return resp


@router.get("/google/callback")
def google_callback(request: Request, code: str = "", state: str = "",
                    db: Session = Depends(get_db)):
    if not code:
        raise HTTPException(400, "Missing code")
    if state != request.cookies.get(STATE_COOKIE, ""):
        raise HTTPException(400, "Invalid OAuth state")
    from .auth import OAUTH_REDIRECT_BASE
    redirect = f"{OAUTH_REDIRECT_BASE}/auth/google/callback"
    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET, "redirect_uri": redirect,
        "grant_type": "authorization_code",
    }, timeout=30)
    if r.status_code != 200:
        raise HTTPException(502, "Google token exchange failed")
    access = r.json()["access_token"]
    info = httpx.get("https://openidconnect.googleapis.com/v1/userinfo",
                     headers={"Authorization": f"Bearer {access}"}, timeout=30).json()
    email = (info.get("email") or "").lower()
    if not email:
        raise HTTPException(502, "Google account has no email")
    user = db.scalars(select(User).where(User.email == email)).first()
    if not user:
        user = User(email=email, name=(info.get("name") or "")[:200],
                    google_sub=info.get("sub"))
        db.add(user)
        db.commit()
        db.refresh(user)
        for name in ("Reading", "Want to read", "Finished"):
            db.add(Shelf(user_id=user.id, name=name))
        db.commit()
    elif not user.google_sub:
        user.google_sub = info.get("sub")
        db.commit()
    frontend = f"{OAUTH_REDIRECT_BASE or ''}/"
    resp = RedirectResponse(url=frontend, status_code=302)
    _set_session(resp, user)
    return resp
