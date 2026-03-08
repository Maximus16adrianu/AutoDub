"""Speaker grouping schemas."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SpeakerEmbedding:
    segment_id: str
    embedding: np.ndarray


@dataclass
class SpeakerClusterResult:
    labels: dict[str, str]
    speaker_count: int


@dataclass
class SpeakerAssignmentResult:
    segment_to_speaker: dict[str, str]
    speaker_count: int
