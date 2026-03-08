"""Final audio/video muxing."""

from __future__ import annotations

from pathlib import Path

from files.media.ffmpeg_service import FFmpegService
from files.media.timeline import RetimedSegment


class MediaMuxer:
    def __init__(self, ffmpeg_service: FFmpegService) -> None:
        self.ffmpeg_service = ffmpeg_service

    def mux_dubbed_audio(
        self,
        source_video: Path,
        dubbed_audio: Path,
        output_video: Path,
        subtitles_path: Path | None = None,
    ) -> Path:
        if subtitles_path:
            intermediate_output = output_video.parent / f"{output_video.stem}_muxed.mp4"
            self._mux_dubbed_audio_copy(source_video, dubbed_audio, intermediate_output)
            self._burn_subtitles(intermediate_output, subtitles_path, output_video)
            if intermediate_output.exists():
                intermediate_output.unlink()
            return output_video
        self._mux_dubbed_audio_copy(source_video, dubbed_audio, output_video)
        return output_video

    def _mux_dubbed_audio_copy(self, source_video: Path, dubbed_audio: Path, output_video: Path) -> Path:
        self.ffmpeg_service.run(
            [
                "-y",
                "-i",
                str(source_video),
                "-i",
                str(dubbed_audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(output_video),
            ]
        )
        return output_video

    def mux_retimed_dubbed_audio(
        self,
        source_video: Path,
        dubbed_audio: Path,
        output_video: Path,
        retimed_segments: list[RetimedSegment],
        subtitles_path: Path | None = None,
    ) -> Path:
        active_segments = [
            segment
            for segment in retimed_segments
            if segment.source_duration > 0.001 and segment.output_duration > 0.001
        ]
        if not active_segments:
            return self.mux_dubbed_audio(source_video, dubbed_audio, output_video, subtitles_path=subtitles_path)
        filter_lines: list[str] = []
        concat_inputs: list[str] = []
        for index, segment in enumerate(active_segments):
            label = f"v{index}"
            factor = segment.output_duration / segment.source_duration
            filter_lines.append(
                f"[0:v]trim=start={segment.source_start:.6f}:end={segment.source_end:.6f},"
                f"setpts={factor:.10f}*(PTS-STARTPTS)[{label}]"
            )
            concat_inputs.append(f"[{label}]")
        filter_lines.append(
            "".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=1:a=0[vout]"
        )
        script_path = output_video.parent / "_retime_video_filters.txt"
        script_path.write_text(";\n".join(filter_lines), encoding="utf-8")
        final_output = output_video
        if subtitles_path:
            final_output = output_video.parent / f"{output_video.stem}_retimed.mp4"
        self.ffmpeg_service.run(
            [
                "-y",
                "-i",
                str(source_video),
                "-i",
                str(dubbed_audio),
                "-filter_complex_script",
                str(script_path),
                "-map",
                "[vout]",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(final_output),
            ]
        )
        if subtitles_path:
            self._burn_subtitles(final_output, subtitles_path, output_video)
            if final_output.exists():
                final_output.unlink()
        return output_video

    def _burn_subtitles(self, source_video: Path, subtitles_path: Path, output_video: Path) -> Path:
        subtitle_filter = (
            f"subtitles='{self._escape_filter_path(subtitles_path)}':"
            "force_style='FontName=Arial,FontSize=18,Outline=1,Shadow=0,MarginV=28'"
        )
        self.ffmpeg_service.run(
            [
                "-y",
                "-i",
                str(source_video),
                "-vf",
                subtitle_filter,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(output_video),
            ]
        )
        return output_video

    def _escape_filter_path(self, path: Path) -> str:
        normalized = str(path.resolve()).replace("\\", "/")
        if len(normalized) > 1 and normalized[1] == ":":
            normalized = normalized[0] + r"\:" + normalized[2:]
        normalized = normalized.replace("'", r"\'")
        normalized = normalized.replace(",", r"\,")
        normalized = normalized.replace("[", r"\[")
        normalized = normalized.replace("]", r"\]")
        return normalized
