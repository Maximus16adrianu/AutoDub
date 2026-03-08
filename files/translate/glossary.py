"""Simple glossary replacement helper."""

from __future__ import annotations


def apply_glossary(text: str, replacements: dict[str, str] | None = None) -> str:
    updated = text
    for source, target in (replacements or {}).items():
        updated = updated.replace(source, target)
    return updated
