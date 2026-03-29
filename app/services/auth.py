from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import firebase_admin
from fastapi import HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.config import Settings

_AUTH_READY = False
_AUTH_ERROR: str | None = None


@dataclass(slots=True)
class AuthenticatedUser:
    user_id: str
    email: str | None = None


def init_auth(settings: Settings) -> None:
    global _AUTH_READY, _AUTH_ERROR

    credentials_path = settings.firebase_credentials_path
    if not credentials_path:
        _AUTH_READY = False
        _AUTH_ERROR = "FIREBASE_CREDENTIALS_PATH is missing."
        return

    if not Path(credentials_path).exists():
        _AUTH_READY = False
        _AUTH_ERROR = f"Firebase credentials file does not exist: {credentials_path}"
        return

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(
            credentials.Certificate(credentials_path),
            {"projectId": settings.firebase_project_id or None},
        )

    _AUTH_READY = True
    _AUTH_ERROR = None


def verify_token(settings: Settings, token: str) -> AuthenticatedUser:
    if not _AUTH_READY and _AUTH_ERROR is None:
        init_auth(settings)

    if not _AUTH_READY:
        detail = _AUTH_ERROR or "Firebase Authentication is not configured."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as error:  # pragma: no cover - delegated to Firebase
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase token.") from error

    return AuthenticatedUser(
        user_id=decoded["uid"],
        email=decoded.get("email"),
    )
