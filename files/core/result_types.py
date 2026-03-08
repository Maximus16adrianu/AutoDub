"""Shared result datatypes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from files.stt.schemas import TranscriptResult


StatusLevel = Literal["ok", "missing", "error", "busy"]
QueueItemStatus = Literal["pending", "running", "completed", "failed"]


@dataclass
class EnvironmentStatusItem:
    key: str
    title: str
    status: StatusLevel
    description: str
    required: bool = True
    details: str = ""
    actions: list[str] = field(default_factory=list)


@dataclass
class EnvironmentSnapshot:
    items: list[EnvironmentStatusItem] = field(default_factory=list)
    checked_at: str = ""
    gpu_available: bool = False
    cuda_available: bool = False
    cache_size_mb: float = 0.0
    last_error: str = ""

    @property
    def ready(self) -> bool:
        return all(item.status == "ok" for item in self.items if item.required)

    def by_key(self) -> dict[str, EnvironmentStatusItem]:
        return {item.key: item for item in self.items}


@dataclass(frozen=True)
class JobRequest:
    source_video: Path
    source_language: str
    target_language: str
    subtitles_enabled: bool
    subtitle_language: str
    retime_video_to_dub: bool
    speaker_grouping_enabled: bool
    voice_mode: str
    max_speaker_voices: int = 3
    auto_match_speaker_gender: bool = False
    preferred_voice_id: str = ""


@dataclass
class QueuedJob:
    queue_id: str
    request: JobRequest
    source_name: str
    status: QueueItemStatus = "pending"
    job_id: str = ""
    error_message: str = ""
    result: JobResult | None = None


@dataclass
class OutputArtifactPaths:
    project_folder: Path
    dubbed_video: Path
    transcript_json: Path
    words_json: Path
    translated_segments_json: Path
    subtitles_srt: Path | None
    metadata_json: Path
    final_mix_wav: Path | None
    speaker_map_json: Path | None = None


@dataclass
class JobResult:
    job_id: str
    request: JobRequest
    transcript: TranscriptResult
    translated_segments: list[dict]
    output_paths: OutputArtifactPaths
    source_language: str
    speaker_map: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    stage: str = "finished"
