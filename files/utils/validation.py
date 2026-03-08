"""Validation helpers."""

from __future__ import annotations

from pathlib import Path

from files.constants import VIDEO_EXTENSIONS


def validate_video_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Video file does not exist: {path}")
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video format: {path.suffix}")
