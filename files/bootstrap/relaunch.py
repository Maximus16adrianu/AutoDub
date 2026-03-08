"""Relaunch helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from files.utils.process_utils import hidden_subprocess_kwargs


def _pythonw_executable() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(executable)


def relaunch_startup(script_path: Path, cwd: Path) -> None:
    subprocess.Popen([_pythonw_executable(), str(script_path)], cwd=str(cwd), **hidden_subprocess_kwargs())
