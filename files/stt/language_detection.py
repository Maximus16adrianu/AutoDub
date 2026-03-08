"""Language detection helpers."""

from __future__ import annotations


def resolve_source_language(requested_language: str, detected_language: str | None) -> str:
    if requested_language and requested_language != "auto":
        return requested_language
    return detected_language or "unknown"
