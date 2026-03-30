from __future__ import annotations

from app.services.domain import SearchResult

DIRECTIVE_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "forget previous instructions",
    "override the instructions",
    "reveal the system prompt",
    "show the system prompt",
    "print the system prompt",
    "show hidden instructions",
    "reveal hidden instructions",
    "use outside knowledge",
    "answer from outside knowledge",
    "answer from your own knowledge",
    "act as ",
)
ROLE_MARKERS = ("system:", "assistant:", "developer:", "tool:")
EXPLANATION_MARKERS = (
    "what does",
    "what is",
    "what are",
    "meaning of",
    "means",
    "example",
    "for example",
    "prompt injection",
    "jailbreak",
)
OUTPUT_LEAK_PATTERNS = (
    "my system prompt",
    "the system prompt says",
    "my hidden instructions",
    "my internal instructions",
    "i was instructed to",
    "developer message says",
)


def detect_user_prompt_injection(text: str) -> str | None:
    normalised = normalise_text(text)
    if looks_explanatory(normalised):
        return None
    if contains_directive_pattern(normalised):
        return "user_prompt_injection"
    return None


def filter_unsafe_results(results: list[SearchResult]) -> tuple[list[SearchResult], int]:
    safe_results: list[SearchResult] = []
    filtered_count = 0

    for result in results:
        if detect_document_prompt_injection(result.chunk.text):
            filtered_count += 1
            continue
        safe_results.append(result)

    return safe_results, filtered_count


def detect_document_prompt_injection(text: str) -> str | None:
    normalised = normalise_text(text)
    if looks_explanatory(normalised):
        return None
    if contains_directive_pattern(normalised):
        return "document_prompt_injection"
    if any(marker in normalised for marker in ROLE_MARKERS):
        return "document_prompt_injection"
    return None


def detect_output_leakage(text: str) -> str | None:
    normalised = normalise_text(text)
    if any(pattern in normalised for pattern in OUTPUT_LEAK_PATTERNS):
        return "model_output_leakage"
    return None


def contains_directive_pattern(text: str) -> bool:
    return any(pattern in text for pattern in DIRECTIVE_PATTERNS)


def looks_explanatory(text: str) -> bool:
    return any(marker in text for marker in EXPLANATION_MARKERS)


def normalise_text(text: str) -> str:
    return " ".join(text.lower().split())
