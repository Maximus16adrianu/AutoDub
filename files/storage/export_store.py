"""Export helpers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from files.storage.project_store import PROJECT_EXPORT_FILE_NAMES
from files.utils.file_utils import ensure_directory


@dataclass(frozen=True)
class ExportBundle:
    project_folder: Path
    export_folder: Path


def copy_project_exports(project_folder: Path, exports_root: Path) -> ExportBundle:
    export_folder = exports_root / project_folder.name
    if export_folder.exists():
        shutil.rmtree(export_folder)
    export_folder = ensure_directory(export_folder)
    for item in project_folder.iterdir():
        if item.name not in PROJECT_EXPORT_FILE_NAMES:
            continue
        destination = export_folder / item.name
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)
    return ExportBundle(project_folder=project_folder, export_folder=export_folder)
