"""Segment chunking helpers."""

from __future__ import annotations

from files.stt.schemas import TranscriptSegment


def chunk_segments(segments: list[TranscriptSegment], max_characters: int = 600) -> list[list[TranscriptSegment]]:
    chunks: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []
    current_size = 0
    for segment in segments:
        segment_size = len(segment.text)
        if current and current_size + segment_size > max_characters:
            chunks.append(current)
            current = []
            current_size = 0
        current.append(segment)
        current_size += segment_size
    if current:
        chunks.append(current)
    return chunks
