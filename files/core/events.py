"""Structured background event types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from files.core.result_types import EnvironmentSnapshot, JobResult


@dataclass(frozen=True)
class JobStarted:
    job_id: str
    project_dir: Path
    created_at: str


@dataclass(frozen=True)
class JobStageChanged:
    job_id: str
    stage: str
    progress: float


@dataclass(frozen=True)
class JobProgress:
    job_id: str
    stage: str
    progress: float
    detail: str


@dataclass(frozen=True)
class JobLog:
    job_id: str
    level: str
    message: str


@dataclass(frozen=True)
class JobFinished:
    job_id: str
    result: JobResult


@dataclass(frozen=True)
class JobFailed:
    job_id: str
    error: str
    technical_details: str = ""


@dataclass(frozen=True)
class BackgroundTaskFailed:
    task_id: str
    error: str
    technical_details: str = ""


@dataclass(frozen=True)
class SetupStatusChanged:
    snapshot: EnvironmentSnapshot


@dataclass(frozen=True)
class SetupScanFailed:
    error: str


@dataclass(frozen=True)
class DownloadProgress:
    component_id: str
    progress: float
    detail: str


@dataclass(frozen=True)
class InstallStarted:
    component_id: str
    title: str


@dataclass(frozen=True)
class InstallFinished:
    component_id: str
    success: bool
    message: str


AppEvent = (
    JobStarted
    | JobStageChanged
    | JobProgress
    | JobLog
    | JobFinished
    | JobFailed
    | BackgroundTaskFailed
    | SetupStatusChanged
    | SetupScanFailed
    | DownloadProgress
    | InstallStarted
    | InstallFinished
    | dict[str, Any]
)
