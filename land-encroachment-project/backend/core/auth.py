from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, request
from werkzeug.security import check_password_hash

from core.db import db_session
from core.responses import error_response


def authenticate_user(db_path: str, username: str, password: str):
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not row or not check_password_hash(row["password"], password):
        return None

    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "full_name": row["full_name"] or row["username"],
    }


def create_token(secret_key: str, expires_minutes: int, user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "full_name": user.get("full_name") or user["username"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_token(secret_key: str, token: str):
    return jwt.decode(token, secret_key, algorithms=["HS256"])


def require_auth(settings, roles=None, allow_legacy=False):
    roles = set(roles or [])

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")

            if not auth_header:
                if allow_legacy and settings.allow_legacy_anonymous:
                    g.current_user = {
                        "id": None,
                        "username": "legacy-anonymous",
                        "role": "admin",
                    }
                    return func(*args, **kwargs)
                return error_response("Authentication required", 401)

            token = auth_header.replace("Bearer ", "", 1).strip()
            if not token:
                return error_response("Authentication required", 401)

            try:
                payload = decode_token(settings.secret_key, token)
            except jwt.ExpiredSignatureError:
                return error_response("Token expired", 401)
            except jwt.InvalidTokenError:
                return error_response("Invalid token", 401)

            g.current_user = payload
            if roles and payload.get("role") not in roles:
                return error_response("Forbidden", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorator
