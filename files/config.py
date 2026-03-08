"""Configuration and runtime path helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .constants import (
    APP_NAME,
    DATA_DIR_NAMES,
    DEFAULT_APPEARANCE_MODE,
    DEFAULT_DEVICE,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_VOICE_MODE,
    DEFAULT_WHISPERX_MODEL,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data: Path
    cache: Path
    logs: Path
    models: Path
    projects: Path
    exports: Path
    settings: Path
    temp: Path
    bootstrap_log: Path
    startup_log: Path
    app_log: Path
    settings_file: Path


@dataclass(frozen=True)
class RuntimeConfig:
    app_name: str
    whisperx_model: str
    appearance_mode: str
    source_language: str
    target_language: str
    voice_mode: str
    preferred_device: str
    sample_rate: int = 16_000
    tts_sample_rate: int = 22_050


def build_paths(root: Path | None = None) -> AppPaths:
    repo_root = root or REPO_ROOT
    data_root = repo_root / "data"
    return AppPaths(
        root=repo_root,
        data=data_root,
        cache=data_root / "cache",
        logs=data_root / "logs",
        models=data_root / "models",
        projects=data_root / "projects",
        exports=data_root / "exports",
        settings=data_root / "settings",
        temp=data_root / "temp",
        bootstrap_log=data_root / "logs" / "bootstrap-install.log",
        startup_log=data_root / "logs" / "startup.log",
        app_log=data_root / "logs" / "app.log",
        settings_file=data_root / "settings" / "settings.json",
    )


def ensure_app_directories(paths: AppPaths | None = None) -> AppPaths:
    resolved = paths or build_paths()
    resolved.data.mkdir(parents=True, exist_ok=True)
    for name in DATA_DIR_NAMES:
        (resolved.data / name).mkdir(parents=True, exist_ok=True)
    return resolved


def configure_runtime_environment(paths: AppPaths | None = None) -> AppPaths:
    resolved = ensure_app_directories(paths)
    os.environ.setdefault("HF_HOME", str(resolved.cache / "huggingface"))
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_CACHE", str(resolved.cache / "transformers"))
    os.environ.setdefault("TORCH_HOME", str(resolved.cache / "torch"))
    os.environ.setdefault("XDG_CACHE_HOME", str(resolved.cache))
    os.environ.setdefault("ARGOS_PACKAGES_DIR", str(resolved.models / "argos"))
    os.environ.setdefault("ARGOS_TRANSLATE_PACKAGE_DIR", str(resolved.models / "argos"))
    os.environ.setdefault("ARGOS_PACKAGE_DIR", str(resolved.models / "argos"))
    os.environ.setdefault("SPEECHBRAIN_CACHE_DIR", str(resolved.models / "speechbrain"))
    return resolved


@lru_cache(maxsize=1)
def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        app_name=APP_NAME,
        whisperx_model=DEFAULT_WHISPERX_MODEL,
        appearance_mode=DEFAULT_APPEARANCE_MODE,
        source_language=DEFAULT_SOURCE_LANGUAGE,
        target_language=DEFAULT_TARGET_LANGUAGE,
        voice_mode=DEFAULT_VOICE_MODE,
        preferred_device=DEFAULT_DEVICE,
    )
