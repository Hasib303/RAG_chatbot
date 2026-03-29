from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, TypeVar
from uuid import uuid4

import firebase_admin
from google.api_core.exceptions import PermissionDenied
from fastapi import HTTPException, status
from firebase_admin import credentials, firestore

from app.config import Settings

T = TypeVar("T")

_DB: firestore.Client | None = None
_DB_ERROR: str | None = None


def init_firestore(settings: Settings) -> None:
    global _DB, _DB_ERROR

    credentials_path = settings.firebase_credentials_path
    if not credentials_path:
        _DB = None
        _DB_ERROR = "FIREBASE_CREDENTIALS_PATH is missing."
        return

    if not Path(credentials_path).exists():
        _DB = None
        _DB_ERROR = f"Firebase credentials file does not exist: {credentials_path}"
        return

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(
            credentials.Certificate(credentials_path),
            {"projectId": settings.firebase_project_id or None},
        )

    _DB = firestore.client()
    _DB_ERROR = None


def create_conversation(settings: Settings, user_id: str, title: str | None = None) -> dict[str, Any]:
    def operation(db: firestore.Client) -> dict[str, Any]:
        conversation_id = uuid4().hex
        now = datetime.now(UTC)
        payload = {
            "user_id": user_id,
            "title": title or "New conversation",
            "document_name": None,
            "document_type": None,
            "document_path": None,
            "created_at": now,
            "updated_at": now,
        }
        db.collection("conversations").document(conversation_id).set(payload)
        return {"id": conversation_id, **payload}

    return run_firestore(settings, operation)


def list_conversations(settings: Settings, user_id: str) -> list[dict[str, Any]]:
    def operation(db: firestore.Client) -> list[dict[str, Any]]:
        snapshots = db.collection("conversations").where("user_id", "==", user_id).stream()
        conversations = [{"id": item.id, **item.to_dict()} for item in snapshots]
        conversations.sort(key=lambda item: item["updated_at"], reverse=True)
        return conversations

    return run_firestore(settings, operation)


def get_conversation(settings: Settings, user_id: str, conversation_id: str) -> dict[str, Any]:
    def operation(db: firestore.Client) -> dict[str, Any]:
        snapshot = db.collection("conversations").document(conversation_id).get()
        if not snapshot.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        conversation = {"id": snapshot.id, **snapshot.to_dict()}
        if conversation["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return conversation

    return run_firestore(settings, operation)


def attach_document( settings: Settings, *, conversation_id: str, document_name: str, document_type: str, document_path: str, ) -> None:
    def operation(db: firestore.Client) -> None:
        now = datetime.now(UTC)
        db.collection("conversations").document(conversation_id).update(
            {
                "title": Path(document_name).stem,
                "document_name": document_name,
                "document_type": document_type,
                "document_path": document_path,
                "updated_at": now,
            }
        )

    run_firestore(settings, operation)


def add_message( settings: Settings, *, conversation_id: str, role: str, content: str, sources: list[dict[str, Any]] | None = None, ) -> dict[str, Any]:
    def operation(db: firestore.Client) -> dict[str, Any]:
        message_id = uuid4().hex
        now = datetime.now(UTC)
        payload = {
            "role": role,
            "content": content,
            "sources": sources or [],
            "created_at": now,
        }
        conversation_ref = db.collection("conversations").document(conversation_id)
        conversation_ref.collection("messages").document(message_id).set(payload)
        conversation_ref.update({"updated_at": now})
        return {"id": message_id, **payload}

    return run_firestore(settings, operation)


def get_messages( settings: Settings, conversation_id: str, limit: int | None = None, ) -> list[dict[str, Any]]:
    def operation(db: firestore.Client) -> list[dict[str, Any]]:
        snapshots = db.collection("conversations").document(conversation_id).collection("messages").stream()
        messages = [{"id": item.id, **item.to_dict()} for item in snapshots]
        messages.sort(key=lambda item: item["created_at"])
        if limit is not None:
            messages = messages[-limit:]
        return messages

    return run_firestore(settings, operation)


def run_firestore(settings: Settings, operation: Callable[[firestore.Client], T]) -> T:
    try:
        db = require_db(settings)
        return operation(db)
    except HTTPException:
        raise
    except PermissionDenied as error:
        project_id = settings.firebase_project_id or "your Firebase project"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Cloud Firestore API is disabled for project '{project_id}'. "
                "Enable Cloud Firestore API in Google Cloud Console, wait a few minutes, and retry."
            ),
        ) from error


def require_db(settings: Settings) -> firestore.Client:
    if _DB is None and _DB_ERROR is None:
        init_firestore(settings)

    if _DB is None:
        detail = _DB_ERROR or "Firebase Firestore is not configured."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return _DB
