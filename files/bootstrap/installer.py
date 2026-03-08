"""Bootstrap-time pip installer."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from files.utils.process_utils import hidden_subprocess_kwargs


class RequirementsInstaller:
    def __init__(self, requirements_file: Path) -> None:
        self.requirements_file = requirements_file

    def install(self, output_callback: Callable[[str], None]) -> None:
        if not self.requirements_file.exists():
            raise FileNotFoundError(f"requirements.txt was not found at {self.requirements_file}")
        command = [sys.executable, "-m", "pip", "install", "-r", str(self.requirements_file)]
        output_callback(f"Running: {' '.join(command)}")
        process = subprocess.Popen(
            command,
            cwd=str(self.requirements_file.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=os.environ.copy(),
            **hidden_subprocess_kwargs(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_callback(line.rstrip())
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"pip install failed with exit code {return_code}")
