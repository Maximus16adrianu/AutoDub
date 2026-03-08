"""FFmpeg and ffprobe discovery plus managed Windows install."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Callable

import requests

from files.storage.settings_store import AppSettings, SettingsStore
from files.utils.file_utils import ensure_directory
from files.utils.process_utils import hidden_subprocess_kwargs


FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


class FFmpegManager:
    def __init__(self, settings_store: SettingsStore, managed_root: Path | None = None) -> None:
        self.settings_store = settings_store
        self.managed_root = managed_root or Path.cwd() / "data" / "models" / "ffmpeg"
        self.managed_root.mkdir(parents=True, exist_ok=True)

    @property
    def archive_path(self) -> Path:
        return self.managed_root / "ffmpeg-release-essentials.zip"

    @property
    def install_root(self) -> Path:
        return self.managed_root / "managed"

    def validate_binary(self, binary_path: str | Path) -> bool:
        if not binary_path:
            return False
        path = Path(binary_path)
        if not path.exists():
            return False
        try:
            completed = subprocess.run(
                [str(path), "-version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
                **hidden_subprocess_kwargs(),
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    def _find_named_binary(self, setting_key: str, binary_name: str) -> str:
        settings = self.settings_store.load()
        saved = getattr(settings, setting_key)
        if saved and self.validate_binary(saved):
            return saved
        managed = self._managed_binary_path(binary_name)
        if self.validate_binary(managed):
            self._save_binary(setting_key, str(managed), settings)
            return str(managed)
        discovered = shutil.which(binary_name)
        if discovered and self.validate_binary(discovered):
            self._save_binary(setting_key, discovered, settings)
            return discovered
        return ""

    def find_ffmpeg(self) -> str:
        return self._find_named_binary("ffmpeg_path", "ffmpeg")

    def find_ffprobe(self) -> str:
        return self._find_named_binary("ffprobe_path", "ffprobe")

    def _save_binary(self, setting_key: str, value: str, settings: AppSettings | None = None) -> None:
        active = settings or self.settings_store.load()
        setattr(active, setting_key, value)
        self.settings_store.save(active)

    def save_ffmpeg_path(self, path: str) -> None:
        if self.validate_binary(path):
            self._save_binary("ffmpeg_path", path)

    def save_ffprobe_path(self, path: str) -> None:
        if self.validate_binary(path):
            self._save_binary("ffprobe_path", path)

    def install_managed_binaries(self, progress_callback: Callable[[str], None] | None = None) -> tuple[str, str]:
        existing_ffmpeg = self.find_ffmpeg()
        existing_ffprobe = self.find_ffprobe()
        if existing_ffmpeg and existing_ffprobe:
            if progress_callback is not None:
                progress_callback("FFmpeg tools are already configured and ready to use.")
            return existing_ffmpeg, existing_ffprobe
        if progress_callback is not None:
            progress_callback("Downloading FFmpeg essentials build for Windows...")
        self._download_file(FFMPEG_DOWNLOAD_URL, self.archive_path, progress_callback)
        if progress_callback is not None:
            progress_callback("Extracting FFmpeg tools...")
        install_root = ensure_directory(self.install_root)
        if install_root.exists():
            shutil.rmtree(install_root, ignore_errors=True)
            install_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.archive_path, "r") as archive:
            archive.extractall(install_root)
        ffmpeg_path = self._locate_extracted_binary("ffmpeg.exe")
        ffprobe_path = self._locate_extracted_binary("ffprobe.exe")
        if ffmpeg_path is None or ffprobe_path is None:
            raise RuntimeError("FFmpeg download completed, but ffmpeg.exe or ffprobe.exe could not be found.")
        self.save_ffmpeg_path(str(ffmpeg_path))
        self.save_ffprobe_path(str(ffprobe_path))
        if progress_callback is not None:
            progress_callback("FFmpeg and ffprobe were installed into the managed tools folder.")
        return str(ffmpeg_path), str(ffprobe_path)

    def is_managed_path(self, binary_path: str | Path) -> bool:
        if not binary_path:
            return False
        try:
            return Path(binary_path).resolve().is_relative_to(self.managed_root.resolve())
        except (OSError, RuntimeError, ValueError):
            return False

    def _managed_binary_path(self, binary_name: str) -> Path:
        candidate = self._locate_extracted_binary(f"{binary_name}.exe")
        return candidate or (self.install_root / "bin" / f"{binary_name}.exe")

    def _locate_extracted_binary(self, binary_name: str) -> Path | None:
        for candidate in self.install_root.glob(f"**/{binary_name}"):
            if candidate.is_file():
                return candidate
        return None

    def _download_file(
        self,
        url: str,
        destination: Path,
        progress_callback: Callable[[str], None] | None = None,
    ) -> Path:
        ensure_directory(destination.parent)
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            total_bytes = int(response.headers.get("Content-Length", "0"))
            downloaded = 0
            last_reported_percent = -1
            with destination.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes and progress_callback is not None:
                        percent = int(downloaded / total_bytes * 100)
                        if percent > last_reported_percent or downloaded >= total_bytes:
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_bytes / (1024 * 1024)
                            progress_callback(
                                f"ffmpeg-release-essentials.zip: {percent:.0f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)"
                            )
                            last_reported_percent = percent
        return destination
