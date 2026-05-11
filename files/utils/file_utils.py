"""Filesystem helpers."""

from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path
from typing import Callable

import requests


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


def safe_extract_zip(archive_path: Path, destination: Path) -> None:
    ensure_directory(destination)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_path, "r") as archive:
        for member in archive.infolist():
            target_path = (destination / member.filename).resolve()
            if not target_path.is_relative_to(destination_root):
                raise RuntimeError(f"Refusing to extract unsafe zip member: {member.filename}")
        archive.extractall(destination)


def download_file_atomic(
    url: str,
    destination: Path,
    progress_callback: Callable[[str], None] | None = None,
    *,
    label: str | None = None,
    timeout: int = 120,
    chunk_size: int = 1024 * 1024,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> Path:
    ensure_directory(destination.parent)
    part_path = destination.with_name(f"{destination.name}.part")
    part_path.unlink(missing_ok=True)
    display_name = label or destination.name
    sha256 = hashlib.sha256() if expected_sha256 else None
    try:
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            header_size = int(response.headers.get("Content-Length", "0") or 0)
            total_bytes = expected_size or header_size
            downloaded = 0
            last_reported_percent = -1
            with part_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    if sha256 is not None:
                        sha256.update(chunk)
                    downloaded += len(chunk)
                    if total_bytes and progress_callback is not None:
                        percent = int(downloaded / total_bytes * 100)
                        if percent > last_reported_percent or downloaded >= total_bytes:
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_bytes / (1024 * 1024)
                            progress_callback(
                                f"{display_name}: {percent:.0f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)"
                            )
                            last_reported_percent = percent
        if header_size and downloaded != header_size:
            raise RuntimeError(f"{display_name} download was incomplete: {downloaded} of {header_size} bytes.")
        if expected_size is not None and downloaded != expected_size:
            raise RuntimeError(f"{display_name} size mismatch: expected {expected_size} bytes, got {downloaded}.")
        if sha256 is not None and expected_sha256 is not None and sha256.hexdigest().lower() != expected_sha256.lower():
            raise RuntimeError(f"{display_name} SHA-256 mismatch.")
        part_path.replace(destination)
        return destination
    except Exception:
        part_path.unlink(missing_ok=True)
        raise
