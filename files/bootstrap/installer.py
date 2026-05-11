"""Bootstrap-time pip installer."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from files.utils.process_utils import hidden_subprocess_kwargs


PYTORCH_CUDA_INDEX_URL = "https://download.pytorch.org/whl/cu128"
PYTORCH_CUDA_PACKAGES = (
    "torch==2.8.0",
    "torchvision==0.23.0",
    "torchaudio==2.8.0",
)


class RequirementsInstaller:
    def __init__(self, requirements_file: Path) -> None:
        self.requirements_file = requirements_file

    @property
    def project_root(self) -> Path:
        return self.requirements_file.parent

    @property
    def venv_dir(self) -> Path:
        return self.project_root / ".venv"

    @property
    def venv_python(self) -> Path:
        return self.venv_dir / "Scripts" / "python.exe"

    def _venv_create_commands(self) -> list[list[str]]:
        commands: list[list[str]] = []
        py_launcher = shutil.which("py")
        if py_launcher:
            commands.append([py_launcher, "-3.10"])
            commands.append([py_launcher, "-3"])
        python = shutil.which("python")
        if python:
            commands.append([python])
        if sys.executable:
            commands.append([sys.executable])
        unique: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()
        for command in commands:
            key = tuple(command)
            if key not in seen:
                unique.append(command)
                seen.add(key)
        return unique

    def _ensure_venv(self, output_callback: Callable[[str], None]) -> Path:
        if self.venv_python.exists():
            return self.venv_python
        output_callback(f"Creating project virtual environment: {self.venv_dir}")
        errors: list[str] = []
        for base_command in self._venv_create_commands():
            command = [*base_command, "-m", "venv", str(self.venv_dir)]
            output_callback(f"Running: {' '.join(command)}")
            completed = subprocess.run(
                command,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=os.environ.copy(),
                **hidden_subprocess_kwargs(),
            )
            if completed.stdout:
                output_callback(completed.stdout.rstrip())
            if completed.stderr:
                output_callback(completed.stderr.rstrip())
            if completed.returncode == 0 and self.venv_python.exists():
                return self.venv_python
            errors.append(f"{' '.join(base_command)} exited with {completed.returncode}")
        joined_errors = "; ".join(errors) or "no Python executable candidates were found"
        raise RuntimeError(f"Could not create the project virtual environment: {joined_errors}")

    def _run_pip_command(self, command: list[str], output_callback: Callable[[str], None]) -> None:
        output_callback(f"Running: {' '.join(command)}")
        process = subprocess.Popen(
            command,
            cwd=str(self.project_root),
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

    def _nvidia_gpu_present(self) -> bool:
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return False
        try:
            completed = subprocess.run(
                [nvidia_smi],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=15,
                **hidden_subprocess_kwargs(),
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    def _install_cuda_torch_if_available(self, venv_python: Path, output_callback: Callable[[str], None]) -> None:
        if not self._nvidia_gpu_present():
            return
        output_callback("NVIDIA GPU detected. Installing CUDA-enabled PyTorch wheels.")
        self._run_pip_command(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--force-reinstall",
                *PYTORCH_CUDA_PACKAGES,
                "--index-url",
                PYTORCH_CUDA_INDEX_URL,
            ],
            output_callback,
        )

    def install(self, output_callback: Callable[[str], None]) -> None:
        if not self.requirements_file.exists():
            raise FileNotFoundError(f"requirements.txt was not found at {self.requirements_file}")
        venv_python = self._ensure_venv(output_callback)
        self._run_pip_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], output_callback)
        self._install_cuda_torch_if_available(venv_python, output_callback)
        self._run_pip_command(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "-r", str(self.requirements_file)],
            output_callback,
        )
