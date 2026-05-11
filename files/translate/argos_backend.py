"""Argos Translate runtime wrapper."""

from __future__ import annotations

from typing import Callable

from files.stt.schemas import TranscriptSegment
from files.translate.context_window import build_neighbor_context
from files.translate.glossary import apply_glossary
from files.translate.package_manager import ArgosPackageManager


class ArgosTranslateBackend:
    def __init__(self, package_manager: ArgosPackageManager) -> None:
        self.package_manager = package_manager

    def _language_api(self):  # type: ignore[no-untyped-def]
        import argostranslate.translate

        return argostranslate.translate

    def available(self) -> bool:
        try:
            self._language_api()
        except Exception:
            return False
        return True

    def ensure_language_pair(
        self,
        source_language: str,
        target_language: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        if source_language == target_language:
            return
        if not self.package_manager.can_translate(source_language, target_language):
            if progress_callback is not None:
                progress_callback(
                    f"Argos translation route missing for {source_language}->{target_language}. Preparing it now."
                )
            self.package_manager.install_language_pair(source_language, target_language, progress_callback)

    def translate_segments(
        self,
        segments: list[TranscriptSegment],
        source_language: str,
        target_language: str,
        glossary: dict[str, str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
        notice_callback: Callable[[str, str], None] | None = None,
        route_label: str = "Main dub translation",
        attach_to_segments: bool = True,
    ) -> list[dict]:
        if source_language == target_language:
            translated_payload: list[dict] = []
            for segment in segments:
                translated = apply_glossary(segment.text, glossary)
                if attach_to_segments:
                    segment.translated_text = translated
                translated_payload.append(
                    {
                        "id": segment.id,
                        "start": segment.start,
                        "end": segment.end,
                        "speaker": segment.speaker,
                        "source_text": segment.text,
                        "translated_text": translated,
                        "language": target_language,
                    }
                )
            return translated_payload

        self.ensure_language_pair(source_language, target_language, progress_callback)
        route = self.package_manager.installed_route(source_language, target_language)
        if route and len(route) > 1 and notice_callback is not None:
            route_text = " -> ".join(step.code for step in route)
            notice_callback(
                f"{route_label} uses a bridge route",
                "No direct Argos package is available for "
                f"{source_language}->{target_language}. AutoDub Studio will continue with "
                f"{route_text}. This means the text is translated in multiple steps and can be less accurate than a direct package.",
            )
        language_api = self._language_api()
        self.package_manager.refresh_translation_cache(language_api)
        translator = language_api.get_translation_from_codes(source_language, target_language)
        translated_payload: list[dict] = []
        for index, segment in enumerate(segments):
            if progress_callback is not None and (
                index == 0
                or (index + 1) == len(segments)
                or ((index + 1) % max(1, len(segments) // 10 or 1) == 0)
            ):
                progress_callback(f"Argos translation progress: {index + 1}/{len(segments)} segments.")
            context = build_neighbor_context(segments, index)
            seed_text = segment.text if not context else f"{context}\n{segment.text}"
            translated_raw = translator.translate(seed_text) or ""
            translated_lines = [line.strip() for line in translated_raw.splitlines() if line.strip()]
            translated = translated_lines[-1] if translated_lines else translated_raw.strip()
            translated = apply_glossary(translated, glossary)
            if attach_to_segments:
                segment.translated_text = translated
            translated_payload.append(
                {
                    "id": segment.id,
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": segment.speaker,
                    "source_text": segment.text,
                    "translated_text": translated,
                    "language": target_language,
                }
            )
        return translated_payload
