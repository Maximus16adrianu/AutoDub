"""Job submission and lifecycle management."""

from __future__ import annotations

import logging
import threading
import traceback
import uuid
from pathlib import Path
from queue import Queue

from files.core.background import BackgroundTaskRunner
from files.core.events import AppEvent, JobFailed, JobFinished, JobLog, JobProgress, JobStageChanged, JobStarted
from files.core.result_types import JobRequest
from files.core.pipeline import Pipeline
from files.storage.project_store import create_project_layout
from files.utils.logging_utils import create_job_logger
from files.utils.text_utils import slugify
from files.utils.time_utils import utc_now_iso
from files.utils.validation import validate_video_file


class JobManager:
    def __init__(self, projects_root: Path, event_queue: Queue[AppEvent], pipeline: Pipeline, logger: logging.Logger) -> None:
        self.projects_root = projects_root
        self.event_queue = event_queue
        self.pipeline = pipeline
        self.logger = logger
        self.background_runner = BackgroundTaskRunner(event_queue, logger)
        self._cancel_events: dict[str, threading.Event] = {}
        self.current_job_id: str | None = None

    def submit(self, request: JobRequest) -> str:
        validate_video_file(request.source_video)
        job_id = f"{slugify(request.source_video.stem)}-{uuid.uuid4().hex[:8]}"
        project_root = self.projects_root / job_id
        layout = create_project_layout(project_root)
        self.current_job_id = job_id
        cancel_event = threading.Event()
        self._cancel_events[job_id] = cancel_event
        job_logger = create_job_logger(layout.log_file, job_id)
        self.event_queue.put(JobStarted(job_id=job_id, project_dir=project_root, created_at=utc_now_iso()))

        def run_job() -> None:
            try:
                result = self.pipeline.run(
                    job_id,
                    request,
                    layout,
                    emit_stage=lambda stage, progress: self._emit_stage(job_id, stage, progress, job_logger),
                    emit_progress=lambda stage, progress, detail: self._emit_progress(job_id, stage, progress, detail),
                    emit_log=lambda message: self._emit_log(job_id, message, job_logger),
                    cancel_event=cancel_event,
                )
            except Exception as exc:
                technical = traceback.format_exc()
                job_logger.exception("Job %s failed.", job_id)
                self.event_queue.put(JobLog(job_id=job_id, level="ERROR", message=str(exc)))
                self.event_queue.put(JobFailed(job_id=job_id, error=str(exc), technical_details=technical))
                return
            job_logger.info("Job %s completed.", job_id)
            self.event_queue.put(JobProgress(job_id=job_id, stage="finished", progress=1.0, detail="Processing complete."))
            self.event_queue.put(JobFinished(job_id=job_id, result=result))

        self.background_runner.submit(job_id, run_job)
        return job_id

    def cancel(self, job_id: str | None = None) -> None:
        active_job_id = job_id or self.current_job_id
        if not active_job_id:
            return
        cancel_event = self._cancel_events.get(active_job_id)
        if cancel_event:
            cancel_event.set()

    def _emit_stage(self, job_id: str, stage: str, progress: float, job_logger: logging.Logger) -> None:
        job_logger.info("Stage changed: %s (%.0f%%)", stage, progress * 100)
        self.event_queue.put(JobStageChanged(job_id=job_id, stage=stage, progress=progress))

    def _emit_log(self, job_id: str, message: str, job_logger: logging.Logger) -> None:
        job_logger.info(message)
        self.event_queue.put(JobLog(job_id=job_id, level="INFO", message=message))

    def _emit_progress(self, job_id: str, stage: str, progress: float, detail: str) -> None:
        self.event_queue.put(JobProgress(job_id=job_id, stage=stage, progress=progress, detail=detail))
