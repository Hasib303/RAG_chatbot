from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:
    import faiss
except ModuleNotFoundError as error:
    raise RuntimeError(
        "Missing dependency 'faiss'. Install 'faiss-cpu' in your environment and restart the app."
    ) from error

from app.config import Settings
from app.services.domain import DocumentChunk, SearchResult

_INDEX_CACHE: dict[str, tuple[faiss.Index, list[DocumentChunk]]] = {}


def save_index( settings: Settings, conversation_id: str, chunks: list[DocumentChunk], embeddings: np.ndarray, ) -> None:
    if not chunks:
        raise ValueError("Cannot create an index with no chunks.")

    metadata_path, faiss_path = index_paths(settings, conversation_id)
    normalised_embeddings = prepare_embeddings(embeddings)
    index = faiss.IndexFlatIP(normalised_embeddings.shape[1])
    index.add(normalised_embeddings)

    write_chunk_metadata(metadata_path, chunks)
    faiss.write_index(index, str(faiss_path))
    remove_legacy_index_files(settings, conversation_id)
    _INDEX_CACHE[conversation_id] = (index, chunks)


def index_exists(settings: Settings, conversation_id: str) -> bool:
    metadata_path, faiss_path = index_paths(settings, conversation_id)
    return metadata_path.exists() and faiss_path.exists()


def query_index( settings: Settings, conversation_id: str, query_embedding: np.ndarray, top_k: int, ) -> list[SearchResult]:
    index, chunks = load_index(settings, conversation_id)
    if not chunks:
        return []

    query_vector = prepare_embeddings(np.asarray(query_embedding).reshape(1, -1))
    limit = min(top_k, len(chunks))
    scores, chunk_ids = index.search(query_vector, limit)
    score_row = scores[0]
    id_row = chunk_ids[0]

    return [
        SearchResult(chunk=chunks[chunk_id], score=float(score))
        for score, chunk_id in zip(score_row, id_row, strict=False)
        if chunk_id >= 0 and score > 0
    ]


def load_index(settings: Settings, conversation_id: str) -> tuple[faiss.Index, list[DocumentChunk]]:
    if conversation_id in _INDEX_CACHE:
        return _INDEX_CACHE[conversation_id]

    metadata_path, faiss_path = index_paths(settings, conversation_id)
    if not metadata_path.exists() or not faiss_path.exists():
        raise FileNotFoundError(f"No vector index found for conversation {conversation_id}.")

    chunk_payloads = json.loads(metadata_path.read_text(encoding="utf-8"))
    chunks = [DocumentChunk.from_dict(payload) for payload in chunk_payloads]
    index = faiss.read_index(str(faiss_path))
    _INDEX_CACHE[conversation_id] = (index, chunks)
    return index, chunks


def remove_legacy_index_files(settings: Settings, conversation_id: str | None = None) -> int:
    if conversation_id is None:
        candidates = settings.indexes_dir.glob("*.npy")
    else:
        candidates = [legacy_index_path(settings, conversation_id)]

    removed_count = 0
    for path in candidates:
        if path.exists():
            path.unlink()
            removed_count += 1
    return removed_count


def index_paths(settings: Settings, conversation_id: str) -> tuple[Path, Path]:
    metadata_path = settings.indexes_dir / f"{conversation_id}.json"
    faiss_path = settings.indexes_dir / f"{conversation_id}.faiss"
    return metadata_path, faiss_path


def legacy_index_path(settings: Settings, conversation_id: str) -> Path:
    return settings.indexes_dir / f"{conversation_id}.npy"


def write_chunk_metadata(path: Path, chunks: list[DocumentChunk]) -> None:
    path.write_text(
        json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def prepare_embeddings(vectors: np.ndarray) -> np.ndarray:
    prepared = np.asarray(vectors, dtype=np.float32)
    prepared = np.atleast_2d(prepared)
    if prepared.size == 0:
        raise ValueError("Cannot prepare an empty embedding matrix.")

    prepared = np.ascontiguousarray(prepared)
    faiss.normalize_L2(prepared)
    return prepared
