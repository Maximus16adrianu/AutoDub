"""Subprocess helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any
from typing import Callable


def hidden_subprocess_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


def run_subprocess(
    command: list[str],
    cwd: Path | None = None,
    input_text: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_kwargs(),
    )
    if input_text is not None and process.stdin is not None:
        process.stdin.write(input_text)
        process.stdin.close()
    output_lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        output_lines.append(line)
        if progress_callback is not None:
            progress_callback(line.rstrip())
    return_code = process.wait()
    output = "".join(output_lines)
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command, output=output)
    return subprocess.CompletedProcess(command, return_code, output, "")
