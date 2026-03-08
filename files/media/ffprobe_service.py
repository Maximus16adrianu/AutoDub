"""ffprobe metadata reader."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from files.utils.process_utils import hidden_subprocess_kwargs


@dataclass(frozen=True)
class MediaProbeResult:
    path: Path
    duration: float
    video_streams: int
    audio_streams: int
    width: int | None = None
    height: int | None = None


class FFProbeService:
    def __init__(self, ffprobe_path: str) -> None:
        self.ffprobe_path = ffprobe_path

    def probe(self, media_path: Path) -> MediaProbeResult:
        command = [
            self.ffprobe_path,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(media_path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            **hidden_subprocess_kwargs(),
        )
        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        format_data = payload.get("format", {})
        video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
        width = video_streams[0].get("width") if video_streams else None
        height = video_streams[0].get("height") if video_streams else None
        return MediaProbeResult(
            path=media_path,
            duration=float(format_data.get("duration", 0.0)),
            video_streams=len(video_streams),
            audio_streams=len(audio_streams),
            width=width,
            height=height,
        )
