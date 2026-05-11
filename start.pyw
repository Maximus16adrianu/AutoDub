"""Bootstrap launcher for AutoDub Studio."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _maybe_relaunch_from_project_venv() -> None:
    root = Path(__file__).resolve().parent
    venv_dir = root / ".venv"
    try:
        running_from_venv = Path(sys.executable).resolve().is_relative_to(venv_dir.resolve())
    except (OSError, RuntimeError, ValueError):
        running_from_venv = False
    if running_from_venv:
        return
    pythonw = venv_dir / "Scripts" / "pythonw.exe"
    python = venv_dir / "Scripts" / "python.exe"
    launcher = pythonw if pythonw.exists() else python
    if not launcher.exists():
        return
    env = os.environ.copy()
    env["AUTODUB_PROJECT_VENV"] = str(venv_dir)
    subprocess.Popen([str(launcher), str(root / "start.pyw")], cwd=str(root), env=env)
    raise SystemExit(0)


_maybe_relaunch_from_project_venv()

from files.bootstrap.bootstrap_window import BootstrapWindow
from files.bootstrap.dependency_check import check_startup_requirements
from files.bootstrap.installer import RequirementsInstaller
from files.bootstrap.relaunch import relaunch_startup
from files.config import build_paths, configure_runtime_environment
from files.utils.logging_utils import configure_startup_logging


def _show_bootstrap(paths, startup_result) -> None:
    installer = RequirementsInstaller(paths.root / "requirements.txt")
    window = BootstrapWindow(
        paths=paths,
        startup_result=startup_result,
        installer=installer,
        launch_callback=lambda: relaunch_startup(paths.root / "start.pyw", paths.root),
    )
    window.run()


def main() -> None:
    paths = configure_runtime_environment(build_paths())
    logger = configure_startup_logging(paths)
    startup_result = check_startup_requirements(paths)
    logger.info("Startup checks complete: %s", startup_result)
    if not startup_result.packages_ready:
        _show_bootstrap(paths, startup_result)
        return
    try:
        from files.app import main as app_main

        app_main()
    except Exception as exc:
        logger.exception("Main application failed to launch.")
        startup_result.status_title = "Main app launch failed"
        startup_result.status_message = (
            "Core Python packages appear to be present, but the main application did not open cleanly. "
            "You can review the log, reinstall packages, and relaunch."
        )
        startup_result.notes.append(f"Main application launch failed: {exc}")
        _show_bootstrap(paths, startup_result)


if __name__ == "__main__":
    main()
