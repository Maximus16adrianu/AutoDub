"""Main application entry point."""

from __future__ import annotations

import logging
from queue import Queue

from files.config import build_paths, configure_runtime_environment
from files.core.events import AppEvent
from files.gui.main_window import MainWindow
from files.setup.environment_manager import EnvironmentManager
from files.setup.ffmpeg_manager import FFmpegManager
from files.setup.model_manager import ModelManager
from files.setup.package_manager import PythonPackageManager
from files.storage.settings_store import SettingsStore
from files.utils.logging_utils import configure_main_logging


def main() -> None:
    paths = configure_runtime_environment(build_paths())
    logger = configure_main_logging(paths)
    logger.info("Launching main application.")
    settings_store = SettingsStore(paths.settings_file)
    ffmpeg_manager = FFmpegManager(settings_store)
    model_manager = ModelManager(paths.models, preferred_device=settings_store.load().preferred_device)
    environment_manager = EnvironmentManager(paths, settings_store, ffmpeg_manager, model_manager)
    package_manager = PythonPackageManager(paths.root / "requirements.txt")
    event_queue: Queue[AppEvent] = Queue()
    window = MainWindow(
        paths=paths,
        settings_store=settings_store,
        ffmpeg_manager=ffmpeg_manager,
        model_manager=model_manager,
        environment_manager=environment_manager,
        python_package_manager=package_manager,
        event_queue=event_queue,
        logger=logger,
    )
    window.mainloop()


if __name__ == "__main__":
    main()
