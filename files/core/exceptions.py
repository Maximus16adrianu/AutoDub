"""Custom exceptions."""

from __future__ import annotations


class AutoDubStudioError(Exception):
    """Base application error."""


class DependencyMissingError(AutoDubStudioError):
    """Raised when a required dependency is not available."""


class PipelineStageError(AutoDubStudioError):
    """Raised when a processing stage fails."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


class UserVisibleError(AutoDubStudioError):
    """Raised for errors that should be shown directly in the GUI."""

