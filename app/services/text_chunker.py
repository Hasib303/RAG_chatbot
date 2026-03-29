from __future__ import annotations

from app.services.domain import DocumentChunk, TextSection


def chunk_sections(
    sections: list[TextSection],
    chunk_size_chars: int,
    chunk_overlap_chars: int,
) -> list[DocumentChunk]:
    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be greater than zero.")
    if chunk_overlap_chars < 0:
        raise ValueError("chunk_overlap_chars cannot be negative.")
    if chunk_overlap_chars >= chunk_size_chars:
        raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars.")

    chunks: list[DocumentChunk] = []
    chunk_number = 1
    step = chunk_size_chars - chunk_overlap_chars

    for section in sections:
        text = section.text.strip()
        if not text:
            continue

        if len(text) <= chunk_size_chars:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk-{chunk_number:04d}",
                    text=text,
                    source_label=section.source_label,
                    page_number=section.page_number,
                )
            )
            chunk_number += 1
            continue

        start = 0
        while start < len(text):
            end = start + chunk_size_chars
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"chunk-{chunk_number:04d}",
                        text=chunk_text,
                        source_label=section.source_label,
                        page_number=section.page_number,
                    )
                )
                chunk_number += 1

            if end >= len(text):
                break
            start += step

    if not chunks:
        raise ValueError("No text chunks were created from the document.")
    return chunks
