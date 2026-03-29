from __future__ import annotations

import json

import numpy as np

from app.config import Settings
from app.services.domain import DocumentChunk, SearchResult

_INDEX_CACHE: dict[str, tuple[np.ndarray, list[DocumentChunk]]] = {}


def save_index(
    settings: Settings,
    conversation_id: str,
    chunks: list[DocumentChunk],
    embeddings: np.ndarray,
) -> None:
    normalised_embeddings = normalise_rows(embeddings)
    metadata_path, embedding_path = index_paths(settings, conversation_id)

    metadata_path.write_text(
        json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    np.save(embedding_path, normalised_embeddings)
    _INDEX_CACHE[conversation_id] = (normalised_embeddings, chunks)


def index_exists(settings: Settings, conversation_id: str) -> bool:
    metadata_path, embedding_path = index_paths(settings, conversation_id)
    return metadata_path.exists() and embedding_path.exists()


def query_index(
    settings: Settings,
    conversation_id: str,
    query_embedding: np.ndarray,
    top_k: int,
) -> list[SearchResult]:
    embeddings, chunks = load_index(settings, conversation_id)
    query_vector = normalise_rows(query_embedding.reshape(1, -1))[0]
    scores = embeddings @ query_vector
    top_indices = np.argsort(scores)[::-1][:top_k]

    return [
        SearchResult(chunk=chunks[index], score=float(scores[index]))
        for index in top_indices
        if scores[index] > 0
    ]


def load_index(settings: Settings, conversation_id: str) -> tuple[np.ndarray, list[DocumentChunk]]:
    if conversation_id in _INDEX_CACHE:
        return _INDEX_CACHE[conversation_id]

    metadata_path, embedding_path = index_paths(settings, conversation_id)
    if not metadata_path.exists() or not embedding_path.exists():
        raise FileNotFoundError(f"No vector index found for conversation {conversation_id}.")

    chunk_payloads = json.loads(metadata_path.read_text(encoding="utf-8"))
    chunks = [DocumentChunk.from_dict(payload) for payload in chunk_payloads]
    embeddings = np.load(embedding_path)
    _INDEX_CACHE[conversation_id] = (embeddings, chunks)
    return embeddings, chunks


def index_paths(settings: Settings, conversation_id: str):
    metadata_path = settings.indexes_dir / f"{conversation_id}.json"
    embedding_path = settings.indexes_dir / f"{conversation_id}.npy"
    return metadata_path, embedding_path


def normalise_rows(matrix: np.ndarray) -> np.ndarray:
    matrix = matrix.astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms
