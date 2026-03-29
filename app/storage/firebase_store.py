from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import firebase_admin
from google.api_core.exceptions import PermissionDenied
from fastapi import HTTPException, status
from firebase_admin import credentials, firestore

_DB = None
_DB_ERROR = None


def init_firestore(settings):
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


def create_conversation(settings, user_id, title=None):
    def operation(db):
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


def list_conversations(settings, user_id):
    def operation(db):
        snapshots = db.collection("conversations").where("user_id", "==", user_id).stream()
        conversations = [{"id": item.id, **item.to_dict()} for item in snapshots]
        conversations.sort(key=lambda item: item["updated_at"], reverse=True)
        return conversations

    return run_firestore(settings, operation)


def get_conversation(settings, user_id, conversation_id):
    def operation(db):
        snapshot = db.collection("conversations").document(conversation_id).get()
        if not snapshot.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        conversation = {"id": snapshot.id, **snapshot.to_dict()}
        if conversation["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return conversation

    return run_firestore(settings, operation)


def attach_document(settings, *, conversation_id, document_name, document_type, document_path):
    def operation(db):
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


def add_message(settings, *, conversation_id, role, content, sources=None):
    def operation(db):
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


def get_messages(settings, conversation_id, limit=None):
    def operation(db):
        snapshots = db.collection("conversations").document(conversation_id).collection("messages").stream()
        messages = [{"id": item.id, **item.to_dict()} for item in snapshots]
        messages.sort(key=lambda item: item["created_at"])
        if limit is not None:
            messages = messages[-limit:]
        return messages

    return run_firestore(settings, operation)


def run_firestore(settings, operation):
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


def require_db(settings):
    if _DB is None and _DB_ERROR is None:
        init_firestore(settings)

    if _DB is None:
        detail = _DB_ERROR or "Firebase Firestore is not configured."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return _DB