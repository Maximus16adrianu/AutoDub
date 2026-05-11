"""Argos language package management."""

from __future__ import annotations

import os
import shutil
from collections import deque
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


@dataclass(frozen=True)
class ArgosRouteStep:
    from_code: str
    to_code: str
    package: object | None = None
    package_label: str = ""

    @property
    def code(self) -> str:
        return f"{self.from_code}->{self.to_code}"

    @property
    def requires_install(self) -> bool:
        return self.package is not None


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

    def _translate_api(self):  # type: ignore[no-untyped-def]
        import argostranslate.translate

        return argostranslate.translate

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

    def can_translate(self, source_language: str, target_language: str) -> bool:
        if source_language == target_language:
            return True
        try:
            translate_api = self._translate_api()
            self.refresh_translation_cache(translate_api)
            translate_api.get_translation_from_codes(source_language, target_language)
        except Exception:
            return False
        return True

    def installed_route(self, source_language: str, target_language: str) -> list[ArgosRouteStep] | None:
        if source_language == target_language:
            return []
        installed_pairs = {(package.from_code, package.to_code) for package in self.list_installed()}
        return self._find_route(source_language, target_language, [], installed_pairs=installed_pairs)

    def install_language_pair(
        self,
        source_language: str,
        target_language: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str:
        if source_language == target_language:
            return "Identity translation"
        if self.can_translate(source_language, target_language):
            return f"{source_language}->{target_language}"
        package_api = self._package_api()
        if progress_callback is not None:
            progress_callback("Updating Argos package index...")
        package_api.update_package_index()
        available_packages = package_api.get_available_packages()
        route = self._find_route(source_language, target_language, available_packages)
        if route is None:
            raise RuntimeError(f"No Argos package route available for {source_language}->{target_language}")
        if progress_callback is not None and len(route) > 1:
            progress_callback(
                "No direct Argos package is available for "
                f"{source_language}->{target_language}. Using route: {' -> '.join(step.code for step in route)}."
            )
        for step in route:
            if not step.requires_install:
                if progress_callback is not None:
                    progress_callback(f"Argos route step already installed: {step.code}.")
                continue
            if progress_callback is not None:
                progress_callback(f"Downloading {step.package_label}...")
            archive_path = Path(step.package.download())
            try:
                package_api.install_from_path(str(archive_path))
            finally:
                archive_path.unlink(missing_ok=True)
        translate_api = self._translate_api()
        self.refresh_translation_cache(translate_api)
        if not self.can_translate(source_language, target_language):
            raise RuntimeError(
                "Argos packages were installed, but no usable translation route became available for "
                f"{source_language}->{target_language}"
            )
        return " -> ".join(step.code for step in route)

    def refresh_translation_cache(self, translate_api=None) -> None:  # type: ignore[no-untyped-def]
        api = translate_api or self._translate_api()
        cache_clear = getattr(api.get_installed_languages, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()

    def _find_route(
        self,
        source_language: str,
        target_language: str,
        available_packages,
        *,
        installed_pairs: set[tuple[str, str]] | None = None,
    ) -> list[ArgosRouteStep] | None:  # type: ignore[no-untyped-def]
        resolved_installed_pairs = installed_pairs or {
            (package.from_code, package.to_code) for package in self.list_installed()
        }
        adjacency: dict[str, list[ArgosRouteStep]] = {}
        seen_available_pairs: set[tuple[str, str]] = set()

        def add_step(step: ArgosRouteStep) -> None:
            adjacency.setdefault(step.from_code, []).append(step)

        for from_code, to_code in resolved_installed_pairs:
            add_step(ArgosRouteStep(from_code=from_code, to_code=to_code))

        for package in available_packages:
            pair = (package.from_code, package.to_code)
            if pair in seen_available_pairs:
                continue
            seen_available_pairs.add(pair)
            add_step(
                ArgosRouteStep(
                    from_code=package.from_code,
                    to_code=package.to_code,
                    package=package,
                    package_label=self._package_label(package),
                )
            )

        for steps in adjacency.values():
            steps.sort(
                key=lambda step: (
                    0 if not step.requires_install else 1,
                    0 if step.to_code == "en" else 1,
                    step.to_code,
                )
            )

        queue: deque[tuple[str, list[ArgosRouteStep]]] = deque([(source_language, [])])
        visited = {source_language}
        while queue:
            current_code, current_route = queue.popleft()
            for step in adjacency.get(current_code, []):
                next_route = [*current_route, step]
                if step.to_code == target_language:
                    return next_route
                if step.to_code in visited:
                    continue
                visited.add(step.to_code)
                queue.append((step.to_code, next_route))
        return None

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
