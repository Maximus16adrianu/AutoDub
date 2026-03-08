"""Central management for fixed-stack installable assets."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Callable

import requests

from files.constants import DEFAULT_WHISPERX_MODEL, WHISPERX_MODEL_PRESETS
from files.setup.model_manifest import InstallableComponent, build_static_manifest
from files.speakers.gender_detection import SpeakerGenderDetector
from files.stt.whisperx_backend import WhisperXBackend
from files.speakers.embedding_backend import SpeechBrainEmbeddingBackend
from files.translate.package_manager import ArgosPackageManager
from files.tts.model_manager import PiperVoiceManager
from files.tts.voice_registry import PIPER_RUNTIME_ZIP_URL, VOICE_REGISTRY, get_voice, voice_ids_for_language
from files.utils.file_utils import ensure_directory


ProgressCallback = Callable[[str], None] | None


class ModelManager:
    def __init__(self, models_root: Path, preferred_device: str = "auto") -> None:
        self.models_root = models_root
        self.whisperx_backend = WhisperXBackend(models_root, preferred_device=preferred_device)
        self.argos_manager = ArgosPackageManager(models_root)
        self.voice_manager = PiperVoiceManager(models_root)
        self.speechbrain_backend = SpeechBrainEmbeddingBackend(models_root)
        self.speaker_gender_detector = SpeakerGenderDetector(models_root)
        self._manifest = build_static_manifest(models_root)

    @property
    def piper_runtime_dir(self) -> Path:
        return self.models_root / "piper" / "runtime"

    def list_components(self) -> list[InstallableComponent]:
        components = list(self._manifest)
        for package in self.argos_manager.list_installed():
            components.append(
                InstallableComponent(
                    id=f"argos-{package.code}",
                    display_name=f"Argos Package {package.from_code}->{package.to_code}",
                    category="argos_package",
                    required=False,
                    local_dir=self.models_root / "argos",
                    description=package.package_name,
                    size_hint="varies",
                    install_method="argos_install",
                    expected_files=(),
                    language_tags=(package.from_code, package.to_code),
                )
            )
        return components

    def get_component(self, component_id: str) -> InstallableComponent:
        for component in self.list_components():
            if component.id == component_id:
                return component
        if component_id.startswith("piper-voice-"):
            voice_id = component_id.replace("piper-voice-", "", 1)
            if voice_id in VOICE_REGISTRY:
                voice = get_voice(voice_id)
                return InstallableComponent(
                    id=component_id,
                    display_name=f"Piper Voice: {voice.display_name}",
                    category="piper_voice",
                    required=False,
                    local_dir=self.models_root / "piper" / voice.voice_id,
                    description=f"{voice.display_name} ({voice.language_code})",
                    size_hint="varies",
                    install_method="piper_download",
                    expected_files=(f"{voice.voice_id}.onnx", f"{voice.voice_id}.onnx.json"),
                    language_tags=(voice.language_code,),
                )
        raise KeyError(component_id)

    def is_installed(self, component_id: str) -> bool:
        component = self.get_component(component_id)
        if component.category == "argos_package":
            from_code, to_code = component.language_tags[:2]
            return self.argos_manager.is_pair_installed(from_code, to_code)
        if component.category == "whisperx_model":
            return (component.local_dir / "model-ready.json").exists()
        if component.category == "speechbrain_asset":
            return self.speechbrain_backend.asset_ready()
        if component.category == "speaker_gender_asset":
            return self.speaker_gender_detector.asset_ready()
        if component.category == "piper_voice":
            voice_id = component.id.replace("piper-voice-", "", 1)
            return self.voice_manager.voice_installed(voice_id)
        return False

    def list_missing_required(self) -> list[InstallableComponent]:
        return [component for component in self._manifest if component.required and not self.is_installed(component.id)]

    def prepared_whisperx_model(self) -> str | None:
        return self.whisperx_backend.prepared_model_name()

    def active_whisperx_model(self) -> str:
        return self.whisperx_backend.active_model_name()

    def install_missing_required(
        self,
        progress_callback: ProgressCallback = None,
        whisperx_model_name: str | None = None,
    ) -> None:
        for component in self.list_missing_required():
            self.install_component(component.id, progress_callback, whisperx_model_name=whisperx_model_name)

    def install_component(
        self,
        component_id: str,
        progress_callback: ProgressCallback = None,
        whisperx_model_name: str | None = None,
    ) -> None:
        component = self.get_component(component_id)
        if progress_callback is not None:
            progress_callback(f"Installing {component.display_name}...")
        if component.install_method == "whisperx_prepare":
            chosen_model = whisperx_model_name or self.whisperx_backend.active_model_name() or DEFAULT_WHISPERX_MODEL
            preset = WHISPERX_MODEL_PRESETS[chosen_model]
            if progress_callback is not None:
                progress_callback(
                    f"Preparing WhisperX {preset.display_name} ({chosen_model}, {preset.size_hint}) as the active transcription model..."
                )
            self.whisperx_backend.prepare_model(chosen_model, progress_callback)
            return
        if component.install_method == "speechbrain_prepare":
            self.speechbrain_backend.prepare_model(progress_callback)
            return
        if component.install_method == "speaker_gender_prepare":
            self.speaker_gender_detector.prepare_model(progress_callback)
            return
        if component.install_method == "piper_download":
            voice_id = component.id.replace("piper-voice-", "", 1)
            self._download_piper_voice(voice_id, progress_callback)
            return
        raise RuntimeError(f"Unsupported install method: {component.install_method}")

    def install_argos_package(
        self,
        source_language: str,
        target_language: str,
        progress_callback: ProgressCallback = None,
    ) -> str:
        return self.argos_manager.install_language_pair(source_language, target_language, progress_callback)

    def ensure_argos_pair(self, source_language: str, target_language: str) -> bool:
        return self.argos_manager.is_pair_installed(source_language, target_language)

    def available_voice_ids_for_language(self, language_code: str, *, balance_gender: bool = False) -> list[str]:
        return voice_ids_for_language(language_code, balance_gender=balance_gender)

    def ensure_voice_pool(
        self,
        language_code: str,
        desired_count: int,
        progress_callback: ProgressCallback = None,
        *,
        balance_gender: bool = False,
    ) -> list[str]:
        if desired_count <= 0:
            return []
        installed_ids = [voice.voice_id for voice in self.voice_manager.get_installed_voices(language_code)]
        available_ids = self.available_voice_ids_for_language(language_code, balance_gender=balance_gender)
        if not available_ids:
            return installed_ids
        if progress_callback is not None and len(installed_ids) < desired_count:
            progress_callback(
                f"Preparing up to {desired_count} Piper voices for {language_code}. "
                f"Currently installed: {len(installed_ids)}."
            )
        for voice_id in available_ids:
            if len(installed_ids) >= desired_count:
                break
            if voice_id in installed_ids:
                continue
            voice = get_voice(voice_id)
            if progress_callback is not None:
                progress_callback(f"Installing extra Piper voice for multi-speaker dubbing: {voice.display_name}")
            self.install_component(f"piper-voice-{voice_id}", progress_callback)
            installed_ids.append(voice_id)
        if progress_callback is not None and len(installed_ids) < desired_count:
            progress_callback(
                f"Only {len(installed_ids)} managed Piper voices are available for {language_code}. "
                "Overflow speakers will reuse voices."
            )
        return installed_ids[: max(1, min(len(installed_ids), desired_count))]

    def remove_component(self, component_id: str) -> None:
        component = self.get_component(component_id)
        if component.category == "argos_package":
            raise RuntimeError("Removing Argos packages is not implemented through this UI flow.")
        if component.local_dir.exists():
            shutil.rmtree(component.local_dir, ignore_errors=True)

    def install_piper_runtime(self, progress_callback: ProgressCallback = None) -> Path:
        runtime_dir = ensure_directory(self.piper_runtime_dir)
        archive_path = runtime_dir / "piper_windows_amd64.zip"
        if progress_callback is not None:
            progress_callback("Downloading Piper Windows runtime...")
        self._download_file(PIPER_RUNTIME_ZIP_URL, archive_path, progress_callback)
        if progress_callback is not None:
            progress_callback("Extracting Piper runtime...")
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(runtime_dir)
        nested_runtime = next(runtime_dir.glob("**/piper.exe"), None)
        if nested_runtime and nested_runtime.parent != runtime_dir:
            for item in nested_runtime.parent.iterdir():
                destination = runtime_dir / item.name
                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()
                if item.is_dir():
                    shutil.copytree(item, destination)
                else:
                    shutil.copy2(item, destination)
        marker_path = runtime_dir / "runtime-ready.json"
        marker_path.write_text(json.dumps({"runtime_path": str(runtime_dir / "piper.exe")}, indent=2), encoding="utf-8")
        return runtime_dir / "piper.exe"

    def piper_runtime_installed(self) -> bool:
        return (self.piper_runtime_dir / "piper.exe").exists()

    def installed_summary(self) -> dict[str, object]:
        prepared_whisperx_model = self.prepared_whisperx_model() or ""
        return {
            "components": {component.id: self.is_installed(component.id) for component in self._manifest},
            "whisperx_model": prepared_whisperx_model,
            "whisperx_model_prepared": bool(prepared_whisperx_model),
            "argos_packages": [package.code for package in self.argos_manager.list_installed()],
            "piper_voices": self.voice_manager.installed_voice_ids(),
            "piper_runtime": self.piper_runtime_installed(),
            "speaker_gender_model": self.speaker_gender_detector.asset_ready(),
        }

    def _download_piper_voice(self, voice_id: str, progress_callback: ProgressCallback = None) -> None:
        voice = get_voice(voice_id)
        voice_dir = ensure_directory(self.models_root / "piper" / voice.voice_id)
        model_path = voice_dir / f"{voice.voice_id}.onnx"
        config_path = voice_dir / f"{voice.voice_id}.onnx.json"
        self._download_file(voice.model_url, model_path, progress_callback)
        self._download_file(voice.config_url, config_path, progress_callback)

    def _download_file(self, url: str, destination: Path, progress_callback: ProgressCallback = None) -> Path:
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
                            progress_callback(f"{destination.name}: {percent:.0f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)")
                            last_reported_percent = percent
        return destination
