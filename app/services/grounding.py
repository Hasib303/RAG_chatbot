from __future__ import annotations

import re

from app.services.domain import SearchResult

FALLBACK_ANSWER = "This information is not present in the provided document."
ABSENCE_PATTERNS = (
    "not mentioned in the provided document",
    "not in the provided document",
    "not present in the provided document",
    "not covered in the provided document",
    "not described in the provided document",
    "not discussed in the provided document",
    "not found in the provided document",
)
IGNORED_QUERY_TERMS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "be",
    "can",
    "does",
    "describe",
    "explain",
    "for",
    "from",
    "how",
    "in",
    "information",
    "is",
    "it",
    "me",
    "model",
    "models",
    "of",
    "on",
    "or",
    "please",
    "say",
    "says",
    "system",
    "systems",
    "tell",
    "text",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}


def should_use_fallback(results: list[SearchResult], score_threshold: float) -> bool:
    if not results:
        return True
    return results[0].score < score_threshold


def question_is_supported(question: str, results: list[SearchResult]) -> bool:
    # A score-only check is too loose for topic-adjacent questions.
    # We also require keyword overlap between the user question and the
    # retrieved chunks before trusting the model to answer.
    query_terms = extract_query_terms(question)
    if not query_terms:
        return True

    context_tokens = collect_context_tokens(results)
    matched_terms = sum(1 for term in query_terms if term_is_present(term, context_tokens))
    required_matches = min(2, len(query_terms))
    return matched_terms >= required_matches


def normalise_answer(answer: str) -> str:
    cleaned = " ".join(answer.split())
    if not cleaned:
        return FALLBACK_ANSWER

    lowered = cleaned.lower()
    if FALLBACK_ANSWER.lower() in lowered:
        return FALLBACK_ANSWER
    if any(pattern in lowered for pattern in ABSENCE_PATTERNS):
        return FALLBACK_ANSWER

    return cleaned


def extract_query_terms(text: str) -> list[str]:
    tokens = tokenise(text)
    query_terms: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        if token in IGNORED_QUERY_TERMS or len(token) < 2 or token.isdigit():
            continue
        if token in seen:
            continue
        seen.add(token)
        query_terms.append(token)

    return query_terms


def collect_context_tokens(results: list[SearchResult]) -> set[str]:
    context_tokens: set[str] = set()
    for result in results:
        context_tokens.update(tokenise(result.chunk.text))
    return context_tokens


def tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def term_is_present(term: str, context_tokens: set[str]) -> bool:
    if term in context_tokens:
        return True
    if f"{term}s" in context_tokens:
        return True
    if term.endswith("s") and term[:-1] in context_tokens:
        return True
    return False
