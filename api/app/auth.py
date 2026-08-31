"""User model + auth utilities: bcrypt password hashing, JWT sessions, Google OAuth."""
import datetime
import os
import secrets

import bcrypt
import jwt as pyjwt

JWT_SECRET = os.environ.get("LIBRARY_JWT_SECRET", "") or secrets.token_hex(32)
JWT_ALG = "HS256"
TOKEN_DAYS = 30

GOOGLE_CLIENT_ID = os.environ.get("LIBRARY_GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("LIBRARY_GOOGLE_CLIENT_SECRET", "")
# where the frontend receives the google callback
OAUTH_REDIRECT_BASE = os.environ.get("LIBRARY_OAUTH_REDIRECT_BASE", "")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user_id: int) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {"sub": str(user_id), "iat": now,
               "exp": now + datetime.timedelta(days=TOKEN_DAYS)}
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> int | None:
    """Returns user_id or None."""
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return int(payload["sub"])
    except (pyjwt.PyJWTError, KeyError, ValueError):
        return None


def google_auth_url(state: str) -> str:
    from urllib.parse import quote
    redirect = f"{OAUTH_REDIRECT_BASE}/auth/google/callback"
    return (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={quote(redirect, safe='')}"
        "&response_type=code&scope=openid%20email%20profile"
        f"&state={quote(state, safe='')}"
        "&access_type=offline&prompt=select_account"
    )
