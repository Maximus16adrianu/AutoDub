"""Relaunch helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from files.utils.process_utils import hidden_subprocess_kwargs


def _project_pythonw(cwd: Path) -> str | None:
    scripts_dir = cwd / ".venv" / "Scripts"
    for filename in ("pythonw.exe", "python.exe"):
        candidate = scripts_dir / filename
        if candidate.exists():
            return str(candidate)
    return None


def _pythonw_executable(cwd: Path) -> str:
    project_python = _project_pythonw(cwd)
    if project_python is not None:
        return project_python
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(executable)


def relaunch_startup(script_path: Path, cwd: Path) -> None:
    subprocess.Popen([_pythonw_executable(cwd), str(script_path)], cwd=str(cwd), **hidden_subprocess_kwargs())
