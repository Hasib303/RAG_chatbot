from __future__ import annotations

from app.services.domain import SearchResult

FALLBACK_ANSWER = "This information is not present in the provided document."


def should_use_fallback(results: list[SearchResult], score_threshold: float) -> bool:
    if not results:
        return True
    return results[0].score < score_threshold


def normalise_answer(answer: str) -> str:
    cleaned = " ".join(answer.split())
    if not cleaned:
        return FALLBACK_ANSWER

    lowered = cleaned.lower()
    if FALLBACK_ANSWER.lower() in lowered:
        return FALLBACK_ANSWER

    return cleaned
