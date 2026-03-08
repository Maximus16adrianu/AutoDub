"""Per-project storage helpers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from files.utils.file_utils import ensure_directory
from files.utils.time_utils import utc_now_iso


PROJECT_EXPORT_FILE_NAMES = {
    "dubbed_video.mp4",
    "metadata.json",
    "transcript.json",
    "translated_segments.json",
    "words.json",
    "speaker_map.json",
    "subtitles.srt",
    "job.log",
}


@dataclass(frozen=True)
class ProjectLayout:
    root: Path
    generated_tts: Path
    metadata_file: Path
    transcript_file: Path
    words_file: Path
    translated_segments_file: Path
    speaker_map_file: Path
    subtitles_file: Path
    extracted_audio_file: Path
    source_mix_file: Path
    dub_voice_mix_file: Path
    background_bed_file: Path
    final_mix_file: Path
    dubbed_video_file: Path
    log_file: Path


def create_project_layout(project_root: Path) -> ProjectLayout:
    ensure_directory(project_root)
    generated_tts = ensure_directory(project_root / "generated_tts")
    return ProjectLayout(
        root=project_root,
        generated_tts=generated_tts,
        metadata_file=project_root / "metadata.json",
        transcript_file=project_root / "transcript.json",
        words_file=project_root / "words.json",
        translated_segments_file=project_root / "translated_segments.json",
        speaker_map_file=project_root / "speaker_map.json",
        subtitles_file=project_root / "subtitles.srt",
        extracted_audio_file=project_root / "extracted_audio.wav",
        source_mix_file=project_root / "source_mix.wav",
        dub_voice_mix_file=project_root / "dub_voice_mix.wav",
        background_bed_file=project_root / "background_bed.wav",
        final_mix_file=project_root / "final_mix.wav",
        dubbed_video_file=project_root / "dubbed_video.mp4",
        log_file=project_root / "job.log",
    )


def new_project_metadata(source_video: str) -> dict[str, str]:
    return {
        "created_at": utc_now_iso(),
        "source_video": source_video,
    }


def prune_project_artifacts(layout: ProjectLayout) -> list[Path]:
    removable_paths = [
        layout.generated_tts,
        layout.extracted_audio_file,
        layout.source_mix_file,
        layout.dub_voice_mix_file,
        layout.background_bed_file,
        layout.final_mix_file,
        layout.root / "_retime_video_filters.txt",
        layout.root / f"{layout.dubbed_video_file.stem}_muxed.mp4",
        layout.root / f"{layout.dubbed_video_file.stem}_retimed.mp4",
    ]
    removed: list[Path] = []
    for path in removable_paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        removed.append(path)
    return removed
