"""Bootstrap launcher for AutoDub Studio."""

from __future__ import annotations

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
