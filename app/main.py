from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    FrontendConfigResponse,
    UploadResponse,
)
from app.services.auth import AuthenticatedUser, init_auth, verify_token
from app.services.rag import (
    answer_conversation as answer_conversation_flow,
    create_conversation as create_conversation_flow,
    get_conversation_detail as get_conversation_detail_flow,
    list_conversations as list_conversations_flow,
    upload_document as upload_document_flow,
)
from app.storage.firebase_store import init_firestore

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

security = HTTPBearer(auto_error=False)
init_auth(settings)
init_firestore(settings)


def get_current_user( credentials: HTTPAuthorizationCredentials | None = Depends(security), ) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
        )
    return verify_token(settings, credentials.credentials)


@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    return FileResponse(settings.index_file)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/frontend-config", response_model=FrontendConfigResponse)
def frontend_config() -> FrontendConfigResponse:
    return FrontendConfigResponse(
        firebase_enabled=settings.firebase_is_configured,
        firebase=settings.firebase_frontend_config,
    )


@app.post("/api/conversations", response_model=ConversationSummary)
def create_conversation( request: CreateConversationRequest, user: AuthenticatedUser = Depends(get_current_user), ) -> ConversationSummary:
    return create_conversation_flow(settings, user, request.title)


@app.get("/api/conversations", response_model=list[ConversationSummary])
def list_conversations(user: AuthenticatedUser = Depends(get_current_user)) -> list[ConversationSummary]:
    return list_conversations_flow(settings, user)


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation( conversation_id: str, user: AuthenticatedUser = Depends(get_current_user), ) -> ConversationDetail:
    return get_conversation_detail_flow(settings, user, conversation_id)


@app.post("/api/upload", response_model=UploadResponse)
def upload_document( conversation_id: str | None = Form(default=None), file: UploadFile = File(...), user: AuthenticatedUser = Depends(get_current_user), ) -> UploadResponse:
    return upload_document_flow(
        settings,
        user=user,
        uploaded_file=file,
        conversation_id=conversation_id,
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat( request: ChatRequest, user: AuthenticatedUser = Depends(get_current_user), ) -> ChatResponse:
    return answer_conversation_flow(
        settings,
        user=user,
        conversation_id=request.conversation_id,
        message=request.message,
        debug=request.debug,
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
