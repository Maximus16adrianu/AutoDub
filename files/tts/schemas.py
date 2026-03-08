"""TTS-related schemas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceSelection:
    voice_id: str
    language_code: str
    display_name: str


@dataclass(frozen=True)
class SynthesizedClip:
    segment_id: str
    speaker: str
    voice_id: str
    output_path: Path
    duration: float
    start: float
    end: float
