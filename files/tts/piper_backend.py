"""Piper runtime wrapper."""

from __future__ import annotations

import importlib.util
import wave
from pathlib import Path

from files.tts.model_manager import PiperVoiceManager
from files.utils.process_utils import run_subprocess


class PiperBackend:
    def __init__(self, models_root: Path, runtime_dir: Path) -> None:
        self.voice_manager = PiperVoiceManager(models_root)
        self.runtime_dir = runtime_dir
        self._voice_cache: dict[str, object] = {}

    @property
    def runtime_path(self) -> Path:
        return self.runtime_dir / "piper.exe"

    def _package_available(self) -> bool:
        return importlib.util.find_spec("piper") is not None

    def available(self) -> bool:
        return self._package_available() or self.runtime_path.exists()

    def _synthesize_with_package(self, text: str, voice_id: str, output_path: Path) -> Path:
        from piper import PiperVoice

        model_path = self.voice_manager.model_path(voice_id)
        voice = self._voice_cache.get(voice_id)
        if voice is None:
            voice = PiperVoice.load(str(model_path))
            self._voice_cache[voice_id] = voice
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)  # type: ignore[attr-defined]
        return output_path

    def _synthesize_with_legacy_executable(self, text: str, voice_id: str, output_path: Path) -> Path:
        model_path = self.voice_manager.model_path(voice_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        run_subprocess(
            [
                str(self.runtime_path),
                "--model",
                str(model_path),
                "--output_file",
                str(output_path),
            ],
            cwd=model_path.parent,
            input_text=text,
        )
        return output_path

    def synthesize(self, text: str, voice_id: str, output_path: Path) -> Path:
        if not self.available():
            raise RuntimeError("Piper runtime is not installed.")
        if not self.voice_manager.voice_installed(voice_id):
            raise RuntimeError(f"Piper voice not installed: {voice_id}")
        if self._package_available():
            return self._synthesize_with_package(text, voice_id, output_path)
        return self._synthesize_with_legacy_executable(text, voice_id, output_path)
