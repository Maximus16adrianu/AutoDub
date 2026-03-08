"""Minimal startup dependency checks."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass, field

from files.constants import CRITICAL_PYTHON_PACKAGES, PYTHON_MIN_VERSION


@dataclass
class StartupCheckResult:
    python_ok: bool
    current_python_version: str
    minimum_python_version: str
    missing_packages: list[str] = field(default_factory=list)
    ffmpeg_found: bool = False
    ffprobe_found: bool = False
    whisperx_model_prepared: bool = False
    piper_runtime_prepared: bool = False
    piper_voice_count: int = 0
    status_title: str = ""
    status_message: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def packages_ready(self) -> bool:
        return self.python_ok and not self.missing_packages

    @property
    def install_allowed(self) -> bool:
        return self.python_ok

    @property
    def missing_items(self) -> list[str]:
        items: list[str] = []
        if not self.python_ok:
            items.append(
                f"Python upgrade required: running {self.current_python_version}, expected {self.minimum_python_version}+"
            )
        if self.missing_packages:
            items.append(f"Python dependencies missing: {', '.join(self.missing_packages)}")
        if not self.ffmpeg_found:
            items.append("FFmpeg was not detected on PATH.")
        if not self.ffprobe_found:
            items.append("ffprobe was not detected on PATH.")
        if not self.whisperx_model_prepared:
            items.append("WhisperX model cache has not been prepared yet.")
        if not self.piper_runtime_prepared:
            items.append("Piper runtime is not installed yet.")
        if self.piper_voice_count == 0:
            items.append("No Piper voice is installed yet.")
        return items


def minimum_python_version_label() -> str:
    return ".".join(str(part) for part in PYTHON_MIN_VERSION)


def find_missing_python_packages() -> list[str]:
    missing = [
        package_name
        for module_name, package_name in CRITICAL_PYTHON_PACKAGES.items()
        if importlib.util.find_spec(module_name) is None
    ]
    return list(dict.fromkeys(missing))


def check_startup_requirements(paths) -> StartupCheckResult:
    python_ok = sys.version_info >= PYTHON_MIN_VERSION
    current_python_version = sys.version.split()[0]
    minimum_version = minimum_python_version_label()
    missing_packages = find_missing_python_packages()
    whisperx_model_prepared = (paths.models / "whisperx" / "model-ready.json").exists()
    piper_runtime_prepared = (paths.models / "piper" / "runtime" / "piper.exe").exists()
    piper_voice_count = len(list((paths.models / "piper").glob("*/*.onnx")))
    notes: list[str] = []
    if not python_ok:
        notes.append(
            f"This launcher is running on Python {current_python_version}. AutoDub Studio currently targets Python {minimum_version}+."
        )
    if missing_packages:
        notes.append(
            f"Required Python packages are missing and can be installed automatically from requirements.txt: {', '.join(missing_packages)}."
        )
    if not shutil.which("ffmpeg"):
        notes.append("FFmpeg is not on PATH yet. That is okay for now; the Setup page can locate it later.")
    if not shutil.which("ffprobe"):
        notes.append("ffprobe is not on PATH yet. That is okay for now; the Setup page can locate it later.")
    if not whisperx_model_prepared:
        notes.append("WhisperX model assets are not prepared yet. The main Setup page can install them.")
    if not piper_runtime_prepared:
        notes.append("Piper runtime is not installed yet. The main Setup page can install it.")
    if piper_voice_count == 0:
        notes.append("No Piper voice files are installed yet. The main Setup page can install one.")
    if python_ok and not missing_packages:
        status_title = "Core runtime ready"
        status_message = "Python and required packages are available. The launcher can start the main CustomTkinter app."
    elif not python_ok:
        status_title = "Python upgrade required"
        status_message = (
            f"Install or launch AutoDub Studio with Python {minimum_version}+ before attempting package installation."
        )
    else:
        status_title = "Dependency installation needed"
        status_message = "Install the required Python packages now, then the launcher will reopen the full app automatically."
    return StartupCheckResult(
        python_ok=python_ok,
        current_python_version=current_python_version,
        minimum_python_version=minimum_version,
        missing_packages=missing_packages,
        ffmpeg_found=bool(shutil.which("ffmpeg")),
        ffprobe_found=bool(shutil.which("ffprobe")),
        whisperx_model_prepared=whisperx_model_prepared,
        piper_runtime_prepared=piper_runtime_prepared,
        piper_voice_count=piper_voice_count,
        status_title=status_title,
        status_message=status_message,
        notes=notes,
    )
