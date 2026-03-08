"""Managed storage paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from files.config import AppPaths, build_paths, configure_runtime_environment


@dataclass(frozen=True)
class ManagedPaths:
    app: AppPaths

    @property
    def projects(self) -> Path:
        return self.app.projects

    @property
    def exports(self) -> Path:
        return self.app.exports

    @property
    def logs(self) -> Path:
        return self.app.logs


def get_managed_paths() -> ManagedPaths:
    return ManagedPaths(configure_runtime_environment(build_paths()))
