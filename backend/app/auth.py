from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response

from .database import connect, transaction
from .rbac import DEFAULT_ROLE, ROLES

SESSION_COOKIE = "civic_records_session"
SESSION_LIFETIME = timedelta(hours=12)
SCRYPT_N = 2**17
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAX_MEMORY = 256 * 1024 * 1024
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
        raise ValueError("Enter a valid email address.")
    return value


def validate_password(password: str) -> None:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    if len(password) > 256:
        raise ValueError("Password must be 256 characters or fewer.")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAX_MEMORY,
        dklen=64,
    )
    salt_value = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_value = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_value}${digest_value}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_value, digest_value = stored_hash.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_value.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_value.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=SCRYPT_MAX_MEMORY,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def create_user(email: str, display_name: str, password: str, role: str = DEFAULT_ROLE) -> dict:
    if role not in ROLES:
        raise ValueError("Unknown role.")
    email = normalize_email(email)
    name = " ".join(display_name.strip().split())
    if len(name) < 2 or len(name) > 80:
        raise ValueError("Display name must be between 2 and 80 characters.")
    password_hash = hash_password(password)
    user_id = str(uuid.uuid4())
    created_at = utc_now()
    try:
        with transaction() as connection:
            connection.execute(
                "INSERT INTO users(id, email, display_name, password_hash, created_at, role) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, email, name, password_hash, created_at, role),
            )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise ValueError("An account with that email already exists.") from exc
        raise
    return {"id": user_id, "email": email, "display_name": name, "role": role, "created_at": created_at}


def user_by_email(email: str) -> dict | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)).fetchone()
    return public_user(row) if row is not None else None


def authenticate_user(email: str, password: str) -> dict | None:
    try:
        email = normalize_email(email)
    except ValueError:
        return None
    with connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return public_user(row)


def issue_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + SESSION_LIFETIME
    with transaction() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (created_at.isoformat(),))
        connection.execute(
            "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, created_at.isoformat(), expires_at.isoformat()),
        )
    return token


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def user_for_request(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = utc_now()
    with connect() as connection:
        row = connection.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > ?""",
            (token_hash, now),
        ).fetchone()
    return public_user(row) if row is not None else None


def revoke_request_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with transaction() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user
