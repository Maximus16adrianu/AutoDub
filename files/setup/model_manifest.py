"""Manifest definitions for installable local assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from files.constants import DEFAULT_PIPER_VOICE_BY_LANGUAGE


ComponentCategory = Literal["whisperx_model", "argos_package", "piper_voice", "speechbrain_asset", "speaker_gender_asset"]


@dataclass(frozen=True)
class InstallableComponent:
    id: str
    display_name: str
    category: ComponentCategory
    required: bool
    local_dir: Path
    description: str
    size_hint: str
    install_method: str
    expected_files: tuple[str, ...] = field(default_factory=tuple)
    language_tags: tuple[str, ...] = field(default_factory=tuple)


def build_static_manifest(models_root: Path) -> list[InstallableComponent]:
    whisperx_dir = models_root / "whisperx"
    piper_dir = models_root / "piper"
    speechbrain_dir = models_root / "speechbrain"
    speaker_gender_dir = models_root / "speaker_gender"
    components = [
        InstallableComponent(
            id="whisperx-default-model",
            display_name="WhisperX Model",
            category="whisperx_model",
            required=True,
            local_dir=whisperx_dir,
            description="Managed WhisperX transcription model. The app asks which size to download before each install.",
            size_hint="varies",
            install_method="whisperx_prepare",
            expected_files=("model-ready.json",),
        ),
        InstallableComponent(
            id="speechbrain-ecapa",
            display_name="SpeechBrain ECAPA Speaker Embedder",
            category="speechbrain_asset",
            required=False,
            local_dir=speechbrain_dir,
            description="Local SpeechBrain cache for best-effort speaker grouping.",
            size_hint="~200 MB",
            install_method="speechbrain_prepare",
            expected_files=("asset-ready.json",),
        ),
        InstallableComponent(
            id="audeering-gender-model",
            display_name="audEERING Speaker Gender Model",
            category="speaker_gender_asset",
            required=False,
            local_dir=speaker_gender_dir,
            description="Managed audEERING age/gender model for better male/female speaker detection.",
            size_hint="~1.2 GB",
            install_method="speaker_gender_prepare",
            expected_files=("asset-ready.json",),
        ),
    ]
    for preset in DEFAULT_PIPER_VOICE_BY_LANGUAGE.values():
        components.append(
            InstallableComponent(
                id=f"piper-voice-{preset.voice_id}",
                display_name=f"Piper Voice: {preset.display_name}",
                category="piper_voice",
                required=preset.language_code == "en",
                local_dir=piper_dir / preset.voice_id,
                description=f"Default {preset.language_code} Piper voice.",
                size_hint="~70 MB",
                install_method="piper_download",
                expected_files=(f"{preset.voice_id}.onnx", f"{preset.voice_id}.onnx.json"),
                language_tags=(preset.language_code,),
            )
        )
    return components


def default_piper_voice_id(language_code: str) -> str:
    preset = DEFAULT_PIPER_VOICE_BY_LANGUAGE.get(language_code)
    return preset.voice_id if preset else DEFAULT_PIPER_VOICE_BY_LANGUAGE["en"].voice_id
