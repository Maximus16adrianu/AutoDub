"""Environment readiness checks and guided setup actions."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable

import torch

from files.bootstrap.dependency_check import find_missing_python_packages
from files.constants import DEFAULT_WHISPERX_MODEL, WHISPERX_MODEL_PRESETS
from files.core.result_types import EnvironmentSnapshot, EnvironmentStatusItem
from files.setup.ffmpeg_manager import FFmpegManager
from files.setup.model_manager import ModelManager
from files.storage.settings_store import SettingsStore
from files.utils.file_utils import clear_directory_contents, directory_size_mb
from files.utils.time_utils import utc_now_iso


class EnvironmentManager:
    def __init__(
        self,
        paths,
        settings_store: SettingsStore,
        ffmpeg_manager: FFmpegManager,
        model_manager: ModelManager,
    ) -> None:
        self.paths = paths
        self.settings_store = settings_store
        self.ffmpeg_manager = ffmpeg_manager
        self.model_manager = model_manager

    def _display_path(self, path_value: str) -> str:
        if not path_value:
            return ""
        path = Path(path_value)
        try:
            return str(path.resolve().relative_to(self.paths.root.resolve()))
        except (OSError, RuntimeError, ValueError):
            return str(path)

    def can_write_directories(self) -> EnvironmentStatusItem:
        try:
            for directory in (
                self.paths.data,
                self.paths.cache,
                self.paths.logs,
                self.paths.models,
                self.paths.projects,
                self.paths.exports,
                self.paths.settings,
                self.paths.temp,
            ):
                directory.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=directory, delete=True):
                    pass
        except Exception as exc:
            return EnvironmentStatusItem(
                key="directories",
                title="App Folders",
                status="error",
                description="The app could not confirm write access to one or more managed folders.",
                details=str(exc),
                actions=["Retry check"],
            )
        return EnvironmentStatusItem(
            key="directories",
            title="App Folders",
            status="ok",
            description="Managed data folders are present and writable.",
            actions=["Open models folder"],
        )

    def check_python_packages(self) -> tuple[EnvironmentStatusItem, list[str]]:
        missing = find_missing_python_packages()
        if missing:
            return (
                EnvironmentStatusItem(
                    key="python_packages",
                    title="Python Packages",
                    status="missing",
                    description="Some required Python packages are missing or not importable yet.",
                    details=f"Install needed: {', '.join(missing)}",
                    actions=["Install missing Python dependencies"],
                ),
                missing,
            )
        return (
            EnvironmentStatusItem(
                key="python_packages",
                title="Python Packages",
                status="ok",
                description="All required Python packages are available to the main app.",
            ),
            [],
        )

    def find_ffmpeg(self) -> EnvironmentStatusItem:
        ffmpeg_path = self.ffmpeg_manager.find_ffmpeg()
        if ffmpeg_path:
            details = self._display_path(ffmpeg_path)
            if self.ffmpeg_manager.is_managed_path(ffmpeg_path):
                details = f"Managed install: {details}"
            return EnvironmentStatusItem(
                key="ffmpeg",
                title="FFmpeg",
                status="ok",
                description="FFmpeg is configured and ready for local media extraction and muxing.",
                details=details,
            )
        return EnvironmentStatusItem(
            key="ffmpeg",
            title="FFmpeg",
            status="missing",
            description="FFmpeg is not configured yet. Install the managed Windows build automatically or locate ffmpeg.exe manually.",
            actions=["Install FFmpeg automatically", "Locate FFmpeg"],
        )

    def find_ffprobe(self) -> EnvironmentStatusItem:
        ffprobe_path = self.ffmpeg_manager.find_ffprobe()
        if ffprobe_path:
            details = self._display_path(ffprobe_path)
            if self.ffmpeg_manager.is_managed_path(ffprobe_path):
                details = f"Managed install: {details}"
            return EnvironmentStatusItem(
                key="ffprobe",
                title="ffprobe",
                status="ok",
                description="ffprobe is configured and ready for stream probing and duration checks.",
                details=details,
            )
        return EnvironmentStatusItem(
            key="ffprobe",
            title="ffprobe",
            status="missing",
            description="ffprobe is not configured yet. Install the managed Windows build automatically or locate ffprobe.exe manually.",
            actions=["Install FFmpeg automatically", "Locate ffprobe"],
        )

    def check_whisperx_ready(self) -> EnvironmentStatusItem:
        if not self.model_manager.whisperx_backend.available():
            return EnvironmentStatusItem(
                key="whisperx_runtime",
                title="WhisperX Runtime",
                status="missing",
                description="WhisperX could not be imported by the current Python environment yet.",
                actions=["Install missing Python dependencies"],
            )
        prepared_model = self.model_manager.prepared_whisperx_model()
        if prepared_model:
            preset = WHISPERX_MODEL_PRESETS.get(prepared_model, WHISPERX_MODEL_PRESETS[DEFAULT_WHISPERX_MODEL])
            return EnvironmentStatusItem(
                key="whisperx_runtime",
                title="WhisperX Model",
                status="ok",
                description="WhisperX runtime is installed and one managed transcription model is ready.",
                details=f"Active model: {preset.display_name} ({prepared_model}, {preset.size_hint}). Install again any time to switch sizes.",
                actions=["Download/install WhisperX model"],
            )
        recommended = WHISPERX_MODEL_PRESETS[DEFAULT_WHISPERX_MODEL]
        return EnvironmentStatusItem(
            key="whisperx_runtime",
            title="WhisperX Model",
            status="missing",
            description="WhisperX runtime is installed, but no managed transcription model has been downloaded yet. The app will ask which model size to install before the download starts.",
            details=f"Recommended starter choice: {recommended.display_name} ({recommended.size_hint}).",
            actions=["Download/install WhisperX model"],
        )

    def check_argos_ready(self) -> EnvironmentStatusItem:
        try:
            installed = self.model_manager.argos_manager.list_installed()
        except Exception:
            return EnvironmentStatusItem(
                key="argos_runtime",
                title="Argos Translate",
                status="missing",
                description="Argos Translate could not be imported by the current Python environment yet.",
                actions=["Install missing Python dependencies"],
            )
        if installed:
            pairs = ", ".join(package.code for package in installed)
            return EnvironmentStatusItem(
                key="argos_runtime",
                title="Argos Translate",
                status="ok",
                description="Argos Translate runtime is installed and offline language packages are already available.",
                details=pairs,
                actions=["Install Argos language packages"],
            )
        return EnvironmentStatusItem(
            key="argos_runtime",
            title="Argos Translate",
            status="ok",
            required=False,
            description="Argos Translate runtime is installed, but no offline language pairs are installed yet.",
            details="Language packages are downloaded only for the source and target languages you choose.",
            actions=["Install Argos language packages"],
        )

    def check_piper_runtime(self) -> EnvironmentStatusItem:
        if self.model_manager.piper_runtime_installed():
            return EnvironmentStatusItem(
                key="piper_runtime",
                title="Piper Runtime",
                status="ok",
                description="The managed Piper runtime is installed and ready to invoke.",
            )
        return EnvironmentStatusItem(
            key="piper_runtime",
            title="Piper Runtime",
            status="missing",
            description="The managed Piper executable is not installed yet. Install it once for local speech synthesis.",
            actions=["Install Piper runtime"],
        )

    def check_piper_voices(self) -> EnvironmentStatusItem:
        installed = self.model_manager.voice_manager.installed_voice_ids()
        if installed:
            return EnvironmentStatusItem(
                key="piper_voice",
                title="Piper Voices",
                status="ok",
                description="At least one Piper voice is installed in the managed model folder.",
                details=", ".join(installed),
                actions=["Install Piper voice"],
            )
        return EnvironmentStatusItem(
            key="piper_voice",
            title="Piper Voices",
            status="missing",
            description="No Piper voice is installed yet. Install at least one voice before generating dubbed speech.",
            actions=["Install Piper voice"],
        )

    def check_speechbrain_ready(self) -> EnvironmentStatusItem:
        try:
            available = self.model_manager.speechbrain_backend.available()
        except Exception:
            available = False
        if available:
            if self.model_manager.is_installed("speechbrain-ecapa"):
                description = "SpeechBrain runtime and the local ECAPA asset are ready for best-effort speaker grouping."
                details = "Used only when one voice per detected speaker is enabled."
            else:
                description = "SpeechBrain runtime is installed, but the local ECAPA asset has not been prepared yet."
                details = "The app can fetch the ECAPA asset later when per-speaker voice mode needs it."
            return EnvironmentStatusItem(
                key="speechbrain_runtime",
                title="SpeechBrain Speaker Grouping",
                status="ok",
                required=False,
                description=description,
                details=details,
                actions=["Prepare SpeechBrain asset"],
            )
        return EnvironmentStatusItem(
            key="speechbrain_runtime",
            title="SpeechBrain Speaker Grouping",
            status="missing",
            required=False,
            description="SpeechBrain runtime is not installed right now, so per-speaker voice mode is unavailable until Python dependencies are fixed.",
            actions=["Install missing Python dependencies"],
        )

    def check_speaker_gender_model(self) -> EnvironmentStatusItem:
        if not self.model_manager.speaker_gender_detector.available():
            return EnvironmentStatusItem(
                key="speaker_gender_model",
                title="audEERING Speaker Gender",
                status="missing",
                required=False,
                description="audonnx/ONNX Runtime are not available yet, so audEERING speaker gender detection cannot run.",
                actions=["Install missing Python dependencies"],
            )
        if self.model_manager.is_installed("audeering-gender-model"):
            return EnvironmentStatusItem(
                key="speaker_gender_model",
                title="audEERING Speaker Gender",
                status="ok",
                required=False,
                description="The audEERING age/gender model is installed for better male/female speaker matching.",
                details="Used only when gender-aware voice matching is enabled in per-speaker mode.",
                actions=["Install audEERING gender model"],
            )
        return EnvironmentStatusItem(
            key="speaker_gender_model",
            title="audEERING Speaker Gender",
            status="missing",
            required=False,
            description="The audEERING age/gender model is not downloaded yet. Install it for better male/female speaker matching.",
            details="The app can also prepare it automatically when a job uses gender-aware speaker matching.",
            actions=["Install audEERING gender model"],
        )

    def check_project_storage(self) -> EnvironmentStatusItem:
        try:
            self.paths.projects.mkdir(parents=True, exist_ok=True)
            self.paths.exports.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return EnvironmentStatusItem(
                key="project_storage",
                title="Project Storage",
                status="error",
                description="The app could not prepare the managed project or export folders.",
                details=str(exc),
            )
        return EnvironmentStatusItem(
            key="project_storage",
            title="Project Storage",
            status="ok",
            description="Managed project and export storage folders are available.",
        )

    def summarize_status(self) -> EnvironmentSnapshot:
        package_item, _missing = self.check_python_packages()
        snapshot = EnvironmentSnapshot(
            items=[
                self.can_write_directories(),
                self.check_project_storage(),
                package_item,
                self.find_ffmpeg(),
                self.find_ffprobe(),
                self.check_whisperx_ready(),
                self.check_argos_ready(),
                self.check_piper_runtime(),
                self.check_piper_voices(),
                self.check_speechbrain_ready(),
                self.check_speaker_gender_model(),
            ],
            checked_at=utc_now_iso(),
            gpu_available=torch.cuda.is_available(),
            cuda_available=torch.cuda.is_available(),
            cache_size_mb=directory_size_mb(self.paths.cache),
        )
        self.settings_store.update(
            {
                "installed_component_metadata_cache": self.model_manager.installed_summary(),
                "last_environment_scan_result": {
                    "checked_at": snapshot.checked_at,
                    "items": [item.__dict__ for item in snapshot.items],
                    "gpu_available": snapshot.gpu_available,
                    "cuda_available": snapshot.cuda_available,
                    "cache_size_mb": snapshot.cache_size_mb,
                },
            }
        )
        return snapshot

    def install_all_missing_required(
        self,
        progress_callback: Callable[[str], None] | None = None,
        whisperx_model_name: str | None = None,
    ) -> None:
        if not self.ffmpeg_manager.find_ffmpeg() or not self.ffmpeg_manager.find_ffprobe():
            if progress_callback is not None:
                progress_callback("Installing managed FFmpeg tools...")
            self.ffmpeg_manager.install_managed_binaries(progress_callback)
        if not self.model_manager.piper_runtime_installed():
            self.model_manager.install_piper_runtime(progress_callback)
        self.model_manager.install_missing_required(progress_callback, whisperx_model_name=whisperx_model_name)

    def clear_cache(self) -> None:
        for item in self.paths.cache.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            elif item.is_file():
                item.unlink(missing_ok=True)

    def remove_all_managed_data(self) -> None:
        managed_directories = (
            self.paths.cache,
            self.paths.logs,
            self.paths.models,
            self.paths.projects,
            self.paths.exports,
            self.paths.settings,
            self.paths.temp,
        )
        for directory in managed_directories:
            directory.mkdir(parents=True, exist_ok=True)
            clear_directory_contents(directory)
        self.paths.data.mkdir(parents=True, exist_ok=True)

    def selected_pair_ready(self, source_language: str, target_language: str) -> bool:
        if source_language == target_language:
            return True
        if source_language == "auto":
            installed = self.model_manager.argos_manager.list_installed()
            return any(package.to_code == target_language for package in installed)
        return self.model_manager.ensure_argos_pair(source_language, target_language)

    def selected_voice_ready(self, target_language: str) -> bool:
        return bool(self.model_manager.voice_manager.get_installed_voices(target_language))
