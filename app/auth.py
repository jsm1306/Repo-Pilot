from __future__ import annotations

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import User

SESSION_COOKIE = "repopilot_session"
CSRF_COOKIE = "repopilot_csrf"
SESSION_TTL_MINUTES = 15
ALLOWED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
logger = logging.getLogger(__name__)


def _required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not configured.")
    return value


def _auth_secret() -> str:
    secret = _required_setting("REPOPILOT_AUTH_SECRET")
    if len(secret) < 32:
        raise RuntimeError("REPOPILOT_AUTH_SECRET must be at least 32 characters.")
    return secret


def _cookie_secure() -> bool:
    return os.getenv("REPOPILOT_COOKIE_SECURE", "false").lower() == "true"


def verify_google_credential(credential: str) -> dict[str, Any]:
    client_id = _required_setting("GOOGLE_CLIENT_ID")
    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            audience=client_id,
        )
    except (ValueError, RuntimeError) as exc:
        raise ValueError("The Google credential is invalid or expired.") from exc

    issuer = claims.get("iss")
    if issuer not in ALLOWED_ISSUERS:
        raise ValueError("The Google credential issuer is invalid.")
    if claims.get("aud") != client_id:
        raise ValueError("The Google credential audience is invalid.")
    if not claims.get("email_verified", False):
        raise ValueError("The Google account email is not verified.")
    if not claims.get("sub") or not claims.get("email"):
        raise ValueError("The Google credential is missing required identity claims.")
    return claims


def create_session_token(user: User) -> str:
    secret = _auth_secret()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "iat": now,
            "exp": now + timedelta(minutes=SESSION_TTL_MINUTES),
            "iss": "repopilot",
        },
        secret,
        algorithm="HS256",
    )


def _decode_session_token(token: str) -> UUID:
    secret = _auth_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], issuer="repopilot")
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise ValueError("The RepoPilot session is invalid.") from exc


def public_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture_url": user.picture_url,
        "is_active": user.is_active,
    }


def set_session_cookies(response: Any, user: User) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user),
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=SESSION_TTL_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        httponly=False,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=SESSION_TTL_MINUTES * 60,
        path="/",
    )


def clear_session_cookies(response: Any) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def require_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "csrf_failed", "message": "The security token is missing or invalid."},
        )


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    if origin and origin not in {"http://127.0.0.1:5173", "http://localhost:5173"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "origin_rejected", "message": "The request origin is not allowed."},
        )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Sign in to continue."},
        )
    try:
        user_id = _decode_session_token(token)
    except (RuntimeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_session", "message": "Your session has expired. Sign in again."},
        ) from None
    try:
        user = db.scalar(select(User).where(User.id == user_id))
    except SQLAlchemyError:
        logger.exception("Could not load authenticated user", extra={"user_id": str(user_id)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "database_unavailable", "message": "The account service is temporarily unavailable."},
        ) from None
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "inactive_account", "message": "This account is inactive."},
        )
    return user
