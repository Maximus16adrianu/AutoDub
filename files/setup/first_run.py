"""First-run state helpers."""

from __future__ import annotations

from files.storage.settings_store import SettingsStore


class FirstRunService:
    def __init__(self, settings_store: SettingsStore) -> None:
        self.settings_store = settings_store

    def is_first_run(self) -> bool:
        settings = self.settings_store.load()
        return not bool(settings.installed_component_metadata_cache)

    def mark_environment_scanned(self, summary: dict) -> None:
        self.settings_store.update({"last_environment_scan_result": summary})
