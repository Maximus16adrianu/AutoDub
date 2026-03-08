"""Python package install helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from files.utils.process_utils import hidden_subprocess_kwargs


class PythonPackageManager:
    def __init__(self, requirements_file: Path) -> None:
        self.requirements_file = requirements_file

    def install_requirements(self, progress_callback: Callable[[str], None] | None = None) -> None:
        command = [sys.executable, "-m", "pip", "install", "-r", str(self.requirements_file)]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            if progress_callback is not None:
                progress_callback(line.rstrip())
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"pip install failed with exit code {return_code}")
