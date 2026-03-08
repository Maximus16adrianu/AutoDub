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
        if not self.package_manager.is_pair_installed(source_language, target_language):
            if progress_callback is not None:
                progress_callback(f"Argos package missing for {source_language}->{target_language}. Downloading it now.")
            self.package_manager.install_language_pair(source_language, target_language, progress_callback)

    def translate_segments(
        self,
        segments: list[TranscriptSegment],
        source_language: str,
        target_language: str,
        glossary: dict[str, str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
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
        language_api = self._language_api()
        languages = {language.code: language for language in language_api.get_installed_languages()}
        source = languages[source_language]
        target = languages[target_language]
        translator = source.get_translation(target)
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
            translated = translator.translate(seed_text).splitlines()[-1].strip()
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
