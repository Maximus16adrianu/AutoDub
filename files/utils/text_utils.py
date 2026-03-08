"""Text helpers."""

from __future__ import annotations

import re


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "job"


def coalesce_text(value: str | None) -> str:
    return (value or "").strip()


def shorten(value: str, limit: int = 80) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
