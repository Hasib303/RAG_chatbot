from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class TextSection:
    text: str
    source_label: str
    page_number: int | None = None


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source_label: str
    page_number: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "DocumentChunk":
        return cls(
            chunk_id=str(payload["chunk_id"]),
            text=str(payload["text"]),
            source_label=str(payload["source_label"]),
            page_number=payload.get("page_number") if payload.get("page_number") is not None else None,
        )


@dataclass(slots=True)
class SearchResult:
    chunk: DocumentChunk
    score: float
