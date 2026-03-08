"""Argos language package management."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from files.utils.file_utils import ensure_directory


@dataclass(frozen=True)
class ArgosLanguagePackage:
    from_code: str
    to_code: str
    package_name: str
    code: str


class ArgosPackageManager:
    def __init__(self, models_root: Path) -> None:
        self.models_root = models_root / "argos"
        self.runtime_root = models_root / "_argos_runtime"
        self.downloads_root = models_root / "_argos_downloads"
        self.package_index_file = self.runtime_root / "index.json"
        self.legacy_cache_root = models_root.parent / "cache" / "argos-translate"
        self.legacy_internal_runtime_root = self.models_root / "_runtime"
        self.legacy_internal_downloads_root = self.models_root / "_downloads"
        ensure_directory(self.models_root)
        ensure_directory(self.runtime_root)
        ensure_directory(self.downloads_root)
        os.environ["ARGOS_PACKAGES_DIR"] = str(self.models_root)
        os.environ["ARGOS_TRANSLATE_PACKAGE_DIR"] = str(self.models_root)
        os.environ["ARGOS_PACKAGE_DIR"] = str(self.models_root)
        self._cleanup_legacy_cache()
        self._cleanup_legacy_internal_dirs()
        self._cleanup_staged_archives()

    def _package_api(self):  # type: ignore[no-untyped-def]
        import argostranslate.settings
        import argostranslate.package

        argostranslate.settings.data_dir = self.runtime_root
        argostranslate.settings.cache_dir = self.runtime_root
        argostranslate.settings.downloads_dir = self.downloads_root
        argostranslate.settings.local_package_index = self.package_index_file
        argostranslate.settings.package_data_dir = self.models_root
        argostranslate.settings.package_dirs = [self.models_root]
        return argostranslate.package

    def _package_label(self, package) -> str:  # type: ignore[no-untyped-def]
        from_name = getattr(package, "from_name", "") or getattr(package, "from_code", "unknown").upper()
        to_name = getattr(package, "to_name", "") or getattr(package, "to_code", "unknown").upper()
        pair = f"{getattr(package, 'from_code', 'unknown')}->{getattr(package, 'to_code', 'unknown')}"
        package_code = getattr(package, "code", "")
        package_version = getattr(package, "package_version", "")
        detail = package_code or pair
        if package_version:
            detail = f"{detail} v{package_version}"
        return f"{from_name} to {to_name} ({detail})"

    def list_installed(self) -> list[ArgosLanguagePackage]:
        package_api = self._package_api()
        packages = []
        for package in package_api.get_installed_packages():
            packages.append(
                ArgosLanguagePackage(
                    from_code=package.from_code,
                    to_code=package.to_code,
                    package_name=self._package_label(package),
                    code=f"{package.from_code}-{package.to_code}",
                )
            )
        return packages

    def is_pair_installed(self, source_language: str, target_language: str) -> bool:
        return any(
            package.from_code == source_language and package.to_code == target_language
            for package in self.list_installed()
        )

    def install_language_pair(
        self,
        source_language: str,
        target_language: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str:
        if source_language == target_language:
            return "Identity translation"
        package_api = self._package_api()
        if progress_callback is not None:
            progress_callback("Updating Argos package index...")
        package_api.update_package_index()
        available_packages = package_api.get_available_packages()
        for package in available_packages:
            if package.from_code == source_language and package.to_code == target_language:
                package_label = self._package_label(package)
                if progress_callback is not None:
                    progress_callback(f"Downloading {package_label}...")
                archive_path = Path(package.download())
                try:
                    package_api.install_from_path(str(archive_path))
                finally:
                    archive_path.unlink(missing_ok=True)
                return package_label
        raise RuntimeError(f"No Argos package available for {source_language}->{target_language}")

    def _cleanup_legacy_cache(self) -> None:
        if not self.legacy_cache_root.exists():
            return
        shutil.rmtree(self.legacy_cache_root, ignore_errors=True)

    def _cleanup_legacy_internal_dirs(self) -> None:
        for path in (self.legacy_internal_runtime_root, self.legacy_internal_downloads_root):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)

    def _cleanup_staged_archives(self) -> None:
        for archive_path in self.downloads_root.glob("*.argosmodel"):
            archive_path.unlink(missing_ok=True)
