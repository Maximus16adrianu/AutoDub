"""Piper runtime wrapper."""

from __future__ import annotations

from pathlib import Path

from files.tts.model_manager import PiperVoiceManager
from files.utils.process_utils import run_subprocess


class PiperBackend:
    def __init__(self, models_root: Path, runtime_dir: Path) -> None:
        self.voice_manager = PiperVoiceManager(models_root)
        self.runtime_dir = runtime_dir

    @property
    def runtime_path(self) -> Path:
        return self.runtime_dir / "piper.exe"

    def available(self) -> bool:
        return self.runtime_path.exists()

    def synthesize(self, text: str, voice_id: str, output_path: Path) -> Path:
        if not self.available():
            raise RuntimeError("Piper runtime is not installed.")
        if not self.voice_manager.voice_installed(voice_id):
            raise RuntimeError(f"Piper voice not installed: {voice_id}")
        model_path = self.voice_manager.model_path(voice_id)
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
