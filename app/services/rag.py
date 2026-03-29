from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.models import (
    ChatDebugInfo,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    MessageResponse,
    SourceSnippet,
    UploadResponse,
)
from app.services.auth import AuthenticatedUser
from app.services.document_parser import parse_document
from app.services.domain import SearchResult
from app.services.grounding import FALLBACK_ANSWER, normalise_answer, should_use_fallback
from app.services.ollama_client import ChatTurn, answer_question, embed_texts
from app.services.text_chunker import chunk_sections
from app.services.vector_store import index_exists, query_index, save_index
from app.storage import firebase_store


def create_conversation(
    settings: Settings,
    user: AuthenticatedUser,
    title: str | None,
) -> ConversationSummary:
    payload = firebase_store.create_conversation(settings, user.user_id, title)
    return ConversationSummary.model_validate(payload)


def list_conversations(settings: Settings, user: AuthenticatedUser) -> list[ConversationSummary]:
    items = firebase_store.list_conversations(settings, user.user_id)
    return [ConversationSummary.model_validate(item) for item in items]


def get_conversation_detail(
    settings: Settings,
    user: AuthenticatedUser,
    conversation_id: str,
) -> ConversationDetail:
    conversation = firebase_store.get_conversation(settings, user.user_id, conversation_id)
    messages = firebase_store.get_messages(settings, conversation_id)
    return ConversationDetail(
        conversation=ConversationSummary.model_validate(conversation),
        messages=[MessageResponse.model_validate(message) for message in messages],
    )


def upload_document(
    settings: Settings,
    *,
    user: AuthenticatedUser,
    uploaded_file: UploadFile,
    conversation_id: str | None,
) -> UploadResponse:
    filename = Path(uploaded_file.filename or "").name
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing file name.")

    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF and DOCX files are supported.")

    if conversation_id:
        conversation = firebase_store.get_conversation(settings, user.user_id, conversation_id)
        if conversation.get("document_name"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This conversation already has a document. Start a new conversation for another file.",
            )
    else:
        conversation = firebase_store.create_conversation(settings, user.user_id, Path(filename).stem)
        conversation_id = conversation["id"]

    upload_path = settings.uploads_dir / f"{conversation_id}{suffix}"
    with upload_path.open("wb") as destination:
        shutil.copyfileobj(uploaded_file.file, destination)

    try:
        chunks = build_chunks_from_document(settings, upload_path)
        embeddings = embed_texts(settings, [chunk.text for chunk in chunks])
    except Exception as error:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not index the document: {error}",
        ) from error
    finally:
        uploaded_file.file.close()

    save_index(settings, conversation_id, chunks, embeddings)
    firebase_store.attach_document(
        settings,
        conversation_id=conversation_id,
        document_name=filename,
        document_type=suffix.lstrip("."),
        document_path=str(upload_path),
    )

    return UploadResponse(
        conversation_id=conversation_id,
        filename=filename,
        chunk_count=len(chunks),
    )


def answer_conversation(
    settings: Settings,
    *,
    user: AuthenticatedUser,
    conversation_id: str,
    message: str,
    debug: bool = False,
) -> ChatResponse:
    conversation = firebase_store.get_conversation(settings, user.user_id, conversation_id)
    document_path = conversation.get("document_path")
    if not document_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a document before starting the chat.",
        )

    try:
        ensure_index(settings, conversation_id, Path(document_path))
        query_embedding = embed_texts(settings, [message])[0]
        search_results = query_index(
            settings,
            conversation_id,
            query_embedding=query_embedding,
            top_k=settings.retrieval_top_k,
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not retrieve document context: {error}",
        ) from error

    used_fallback = should_use_fallback(search_results, settings.retrieval_score_threshold)
    if used_fallback:
        answer = FALLBACK_ANSWER
    else:
        recent_messages = firebase_store.get_messages(
            settings,
            conversation_id,
            limit=settings.max_history_messages,
        )
        history = [ChatTurn(role=item["role"], content=item["content"]) for item in recent_messages]

        try:
            raw_answer = answer_question(
                settings,
                question=message,
                search_results=search_results,
                history=history,
            )
            answer = normalise_answer(raw_answer)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not generate an answer with Ollama: {error}",
            ) from error

    sources = serialise_sources(search_results[:3]) if answer != FALLBACK_ANSWER else []
    debug_info = build_debug_info(settings, search_results, used_fallback) if debug else None

    firebase_store.add_message(
        settings,
        conversation_id=conversation_id,
        role="user",
        content=message,
    )
    firebase_store.add_message(
        settings,
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        sources=[source.model_dump() for source in sources],
    )

    return ChatResponse(answer=answer, sources=sources, debug=debug_info)


def build_chunks_from_document(settings: Settings, document_path: Path):
    sections = parse_document(document_path)
    return chunk_sections(
        sections,
        chunk_size_chars=settings.chunk_size_chars,
        chunk_overlap_chars=settings.chunk_overlap_chars,
    )


def ensure_index(settings: Settings, conversation_id: str, document_path: Path) -> None:
    if index_exists(settings, conversation_id):
        return

    chunks = build_chunks_from_document(settings, document_path)
    embeddings = embed_texts(settings, [chunk.text for chunk in chunks])
    save_index(settings, conversation_id, chunks, embeddings)


def serialise_sources(results: list[SearchResult]) -> list[SourceSnippet]:
    return [
        SourceSnippet(
            chunk_id=result.chunk.chunk_id,
            source_label=result.chunk.source_label,
            score=round(result.score, 3),
            text=result.chunk.text,
        )
        for result in results
    ]


def build_debug_info(
    settings: Settings,
    results: list[SearchResult],
    used_fallback: bool,
) -> ChatDebugInfo:
    return ChatDebugInfo(
        used_fallback=used_fallback,
        score_threshold=settings.retrieval_score_threshold,
        top_score=round(results[0].score, 3) if results else None,
        matches=serialise_sources(results[: settings.retrieval_top_k]),
    )
