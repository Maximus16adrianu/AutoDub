"""Health check wrapper."""

from __future__ import annotations

from files.core.result_types import EnvironmentSnapshot
from files.setup.environment_manager import EnvironmentManager


class HealthCheckService:
    def __init__(self, environment_manager: EnvironmentManager) -> None:
        self.environment_manager = environment_manager

    def run(self) -> EnvironmentSnapshot:
        return self.environment_manager.summarize_status()
