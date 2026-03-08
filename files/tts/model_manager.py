"""Piper voice lookup helpers."""

from __future__ import annotations

from pathlib import Path

from files.constants import DEFAULT_PIPER_VOICE_BY_LANGUAGE
from files.tts.voice_registry import VOICE_REGISTRY, PiperVoice, voices_for_language


class PiperVoiceManager:
    def __init__(self, models_root: Path) -> None:
        self.voices_root = models_root / "piper"
        self.voices_root.mkdir(parents=True, exist_ok=True)

    def installed_voice_ids(self) -> list[str]:
        installed: list[str] = []
        for voice_id in VOICE_REGISTRY:
            model_path = self.model_path(voice_id)
            config_path = self.config_path(voice_id)
            if model_path.exists() and config_path.exists():
                installed.append(voice_id)
        return installed

    def get_installed_voices(self, language_code: str | None = None) -> list[PiperVoice]:
        voices = [VOICE_REGISTRY[voice_id] for voice_id in self.installed_voice_ids()]
        if language_code is None:
            return voices
        return [voice for voice in voices if voice.language_code == language_code]

    def default_voice_for_language(self, language_code: str) -> str:
        preset = DEFAULT_PIPER_VOICE_BY_LANGUAGE.get(language_code)
        if preset and self.voice_installed(preset.voice_id):
            return preset.voice_id
        installed = self.get_installed_voices(language_code)
        if installed:
            return installed[0].voice_id
        fallback_installed = self.get_installed_voices()
        if fallback_installed:
            return fallback_installed[0].voice_id
        fallback_registry = voices_for_language(language_code)
        if fallback_registry:
            return fallback_registry[0].voice_id
        return DEFAULT_PIPER_VOICE_BY_LANGUAGE["en"].voice_id

    def voice_installed(self, voice_id: str) -> bool:
        return self.model_path(voice_id).exists() and self.config_path(voice_id).exists()

    def model_path(self, voice_id: str) -> Path:
        return self.voices_root / voice_id / f"{voice_id}.onnx"

    def config_path(self, voice_id: str) -> Path:
        return self.voices_root / voice_id / f"{voice_id}.onnx.json"
