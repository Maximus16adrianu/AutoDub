"""Basic audio normalization."""

from __future__ import annotations

from pathlib import Path

from files.media.ffmpeg_service import FFmpegService


class AudioNormalizer:
    def __init__(self, ffmpeg_service: FFmpegService) -> None:
        self.ffmpeg_service = ffmpeg_service

    def normalize(self, input_audio: Path, output_audio: Path) -> Path:
        self.ffmpeg_service.run(
            [
                "-y",
                "-i",
                str(input_audio),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                str(output_audio),
            ]
        )
        return output_audio
