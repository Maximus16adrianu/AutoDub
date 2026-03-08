"""FFmpeg subprocess wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from files.utils.process_utils import run_subprocess


class FFmpegService:
    def __init__(self, ffmpeg_path: str) -> None:
        self.ffmpeg_path = ffmpeg_path

    def run(self, arguments: list[str], progress_callback: Callable[[str], None] | None = None) -> str:
        command = [self.ffmpeg_path, *arguments]
        completed = run_subprocess(command, progress_callback=progress_callback)
        return completed.stdout

    def exists(self) -> bool:
        return bool(self.ffmpeg_path and Path(self.ffmpeg_path).exists())
