"""Context helpers for segment translation."""

from __future__ import annotations

from files.stt.schemas import TranscriptSegment


def build_neighbor_context(segments: list[TranscriptSegment], index: int, radius: int = 1) -> str:
    start = max(0, index - radius)
    end = min(len(segments), index + radius + 1)
    window = [segments[item].text for item in range(start, end) if item != index]
    return " ".join(text for text in window if text).strip()
