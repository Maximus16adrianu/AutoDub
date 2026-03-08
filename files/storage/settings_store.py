"""Application settings persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from files.constants import (
    DEFAULT_APPEARANCE_MODE,
    DEFAULT_AUTO_MATCH_SPEAKER_GENDER,
    DEFAULT_DEVICE,
    DEFAULT_MAX_SPEAKER_VOICES,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_RETIME_VIDEO_TO_DUB,
    DEFAULT_SUBTITLES_ENABLED,
    DEFAULT_SUBTITLE_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_VOICE_MODE,
)
from files.storage.json_store import JsonStore


@dataclass
class AppSettings:
    appearance_mode: str = DEFAULT_APPEARANCE_MODE
    ffmpeg_path: str = ""
    ffprobe_path: str = ""
    default_source_language: str = DEFAULT_SOURCE_LANGUAGE
    default_target_language: str = DEFAULT_TARGET_LANGUAGE
    default_voice_mode: str = DEFAULT_VOICE_MODE
    default_max_speaker_voices: int = DEFAULT_MAX_SPEAKER_VOICES
    auto_match_speaker_gender: bool = DEFAULT_AUTO_MATCH_SPEAKER_GENDER
    subtitles_enabled: bool = DEFAULT_SUBTITLES_ENABLED
    default_subtitle_language: str = DEFAULT_SUBTITLE_LANGUAGE
    retime_video_to_dub: bool = DEFAULT_RETIME_VIDEO_TO_DUB
    speaker_grouping_enabled: bool = False
    preferred_device: str = DEFAULT_DEVICE
    last_opened_file: str = ""
    last_used_piper_voice_by_language: dict[str, str] = field(default_factory=dict)
    installed_component_metadata_cache: dict[str, Any] = field(default_factory=dict)
    last_environment_scan_result: dict[str, Any] = field(default_factory=dict)
    recent_projects: list[str] = field(default_factory=list)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._store = JsonStore(path)

    def load(self) -> AppSettings:
        raw = self._store.load(default={})
        return AppSettings(**raw)

    def save(self, settings: AppSettings) -> None:
        self._store.save(asdict(settings))

    def update(self, updater: dict[str, Any]) -> AppSettings:
        current = self.load()
        for key, value in updater.items():
            if hasattr(current, key):
                setattr(current, key, value)
        self.save(current)
        return current
