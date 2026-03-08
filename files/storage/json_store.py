"""JSON file persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from files.utils.file_utils import ensure_directory
from files.utils.json_utils import make_json_safe


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, default: Any) -> Any:
        if not self.path.exists():
            return default
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, value: Any) -> None:
        ensure_directory(self.path.parent)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(make_json_safe(value), handle, indent=2, ensure_ascii=False)
