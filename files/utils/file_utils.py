"""Filesystem helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_copy(source: Path, destination: Path) -> Path:
    ensure_directory(destination.parent)
    shutil.copy2(source, destination)
    return destination


def clear_directory_contents(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            continue
        try:
            item.unlink(missing_ok=True)
        except PermissionError:
            try:
                item.write_text("", encoding="utf-8")
            except OSError:
                pass


def file_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return round(path.stat().st_size / (1024 * 1024), 2)


def directory_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return round(total / (1024 * 1024), 2)


def open_in_explorer(path: Path) -> None:
    os.startfile(str(path))
