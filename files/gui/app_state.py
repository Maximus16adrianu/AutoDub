"""Shared mutable UI state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from files.core.result_types import EnvironmentSnapshot, JobResult, QueuedJob
from files.storage.settings_store import AppSettings


@dataclass
class AppState:
    current_page: str = "Setup"
    selected_file: Path | None = None
    source_language: str = "auto"
    target_language: str = "en"
    subtitles_enabled: bool = True
    subtitle_language: str = "target"
    retime_video_to_dub: bool = True
    speaker_grouping_enabled: bool = False
    voice_mode: str = "single"
    max_speaker_voices: int = 3
    auto_match_speaker_gender: bool = False
    environment_snapshot: EnvironmentSnapshot | None = None
    current_job_id: str | None = None
    latest_result: JobResult | None = None
    settings: AppSettings | None = None
    installed_components_summary: dict[str, object] = field(default_factory=dict)
    preferred_voice_id: str = ""
    queued_jobs: list[QueuedJob] = field(default_factory=list)
    queue_running: bool = False
    active_queue_item_id: str | None = None
