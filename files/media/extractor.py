"""Audio extraction helpers."""

from __future__ import annotations

from pathlib import Path

from files.media.ffmpeg_service import FFmpegService


class AudioExtractor:
    def __init__(self, ffmpeg_service: FFmpegService) -> None:
        self.ffmpeg_service = ffmpeg_service

    def extract_wav(self, video_path: Path, output_path: Path, sample_rate: int = 16_000) -> Path:
        self.ffmpeg_service.run(
            [
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-sample_fmt",
                "s16",
                str(output_path),
            ]
        )
        return output_path

    def extract_source_mix(self, video_path: Path, output_path: Path, sample_rate: int = 22_050) -> Path:
        self.ffmpeg_service.run(
            [
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "2",
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ]
        )
        return output_path
