"""Background worker execution with event queue handoff."""

from __future__ import annotations

import logging
import threading
from queue import Queue
from typing import Callable, ParamSpec, TypeVar

from files.core.events import AppEvent, BackgroundTaskFailed, JobLog

P = ParamSpec("P")
R = TypeVar("R")


class BackgroundTaskRunner:
    def __init__(self, event_queue: Queue[AppEvent], logger: logging.Logger) -> None:
        self.event_queue = event_queue
        self.logger = logger
        self._threads: dict[str, threading.Thread] = {}

    def submit(self, task_id: str, target: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> None:
        def runner() -> None:
            try:
                target(*args, **kwargs)
            except Exception as exc:
                self.logger.exception("Background task %s failed.", task_id)
                self.event_queue.put(JobLog(job_id=task_id, level="ERROR", message=str(exc)))
                self.event_queue.put(BackgroundTaskFailed(task_id=task_id, error=str(exc), technical_details=repr(exc)))

        thread = threading.Thread(target=runner, name=f"task-{task_id}", daemon=True)
        self._threads[task_id] = thread
        thread.start()

    def is_running(self, task_id: str) -> bool:
        thread = self._threads.get(task_id)
        return bool(thread and thread.is_alive())
