"""Transcript schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WordToken:
    id: str
    text: str
    start: float
    end: float
    confidence: float | None = None
    speaker: str | None = None
    segment_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptSegment:
    id: str
    start: float
    end: float
    text: str
    language: str
    speaker: str | None = None
    word_ids: list[str] = field(default_factory=list)
    translated_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class TranscriptResult:
    source_language: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    words: list[WordToken] = field(default_factory=list)
    duration: float | None = None
    speaker_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_language": self.source_language,
            "segments": [segment.to_dict() for segment in self.segments],
            "words": [word.to_dict() for word in self.words],
            "duration": self.duration,
            "speaker_count": self.speaker_count,
        }

