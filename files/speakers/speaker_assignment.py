"""Speaker assignment service."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from files.constants import SPEAKER_LABEL_TEMPLATE
from files.speakers.clustering import choose_cluster_labels, normalize_embeddings
from files.speakers.embedding_backend import SpeechBrainEmbeddingBackend
from files.speakers.schemas import SpeakerAssignmentResult
from files.stt.schemas import TranscriptResult

MIN_STABLE_SEGMENT_DURATION = 0.7
MIN_STABLE_SEGMENT_ENERGY = 0.005
MIN_STABLE_SEGMENTS = 6
MAX_SINGLETON_SEGMENT_DURATION = 1.2
MAX_SMOOTHING_GAP = 1.0
MIN_ASSIGNMENT_SEGMENT_DURATION = 0.25
ASSIGNMENT_ENERGY_FACTOR = 0.5
SNIPPET_PADDING_SECONDS = 0.15


class SpeakerAssignmentService:
    def __init__(self, embedding_backend: SpeechBrainEmbeddingBackend) -> None:
        self.embedding_backend = embedding_backend

    def assign(
        self,
        audio_path: Path,
        transcript: TranscriptResult,
        max_speakers_hint: int | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> SpeakerAssignmentResult:
        if not transcript.segments:
            return SpeakerAssignmentResult(segment_to_speaker={}, speaker_count=0)
        self.embedding_backend.ensure_ready(progress_callback)
        audio, sample_rate = sf.read(str(audio_path), dtype="float32")
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)

        segment_ids: list[str] = []
        segment_snippets: list[np.ndarray] = []
        stable_embeddings: list[np.ndarray] = []
        stable_indices: list[int] = []
        for index, segment in enumerate(transcript.segments):
            snippet = self._segment_snippet(audio, sample_rate, segment.start, segment.end)
            segment_snippets.append(snippet)
            segment_ids.append(segment.id)
            if segment.duration >= MIN_STABLE_SEGMENT_DURATION and self._snippet_energy(snippet) >= MIN_STABLE_SEGMENT_ENERGY:
                try:
                    stable_embeddings.append(
                        normalize_embeddings(
                            np.expand_dims(self.embedding_backend.extract_embedding(snippet, progress_callback), axis=0)
                        )[0]
                    )
                    stable_indices.append(index)
                except Exception:
                    if progress_callback is not None:
                        progress_callback(f"Skipping one speaker-grouping snippet at segment {index + 1} because embedding extraction failed.")

        cluster_source_indices = stable_indices
        cluster_source_embeddings = np.vstack(stable_embeddings) if stable_embeddings else np.empty((0, 0), dtype=np.float32)
        if len(cluster_source_indices) < MIN_STABLE_SEGMENTS:
            cluster_source_indices = []
            fallback_embeddings: list[np.ndarray] = []
            for index, snippet in enumerate(segment_snippets):
                if self._snippet_energy(snippet) < MIN_STABLE_SEGMENT_ENERGY * ASSIGNMENT_ENERGY_FACTOR:
                    continue
                try:
                    fallback_embeddings.append(
                        normalize_embeddings(
                            np.expand_dims(self.embedding_backend.extract_embedding(snippet, progress_callback), axis=0)
                        )[0]
                    )
                    cluster_source_indices.append(index)
                except Exception:
                    if progress_callback is not None:
                        progress_callback(f"Skipping one fallback speaker-grouping snippet at segment {index + 1}.")
            if fallback_embeddings:
                cluster_source_embeddings = np.vstack(fallback_embeddings)
        if len(cluster_source_indices) == 0:
            cluster_source_indices = [0]
            try:
                cluster_source_embeddings = normalize_embeddings(
                    np.expand_dims(self.embedding_backend.extract_embedding(segment_snippets[0], progress_callback), axis=0)
                )
            except Exception as exc:
                raise RuntimeError("Speaker grouping could not extract any usable ECAPA embeddings.") from exc
        discovered_label_ids = choose_cluster_labels(cluster_source_embeddings, max_speakers=max_speakers_hint)
        centroids = self._build_centroids(cluster_source_embeddings, discovered_label_ids)
        label_ids = self._assign_segments_to_centroids(segment_snippets, transcript, centroids, progress_callback)
        label_ids = self._smooth_temporal_islands(label_ids, transcript)
        labels = self._format_labels(label_ids)
        mapping = dict(zip(segment_ids, labels, strict=False))
        for segment in transcript.segments:
            segment.speaker = mapping.get(segment.id)
        for word in transcript.words:
            if word.segment_id:
                word.speaker = mapping.get(word.segment_id)
        speaker_count = len(set(mapping.values()))
        transcript.speaker_count = speaker_count
        return SpeakerAssignmentResult(segment_to_speaker=mapping, speaker_count=speaker_count)

    def _segment_snippet(
        self,
        audio: np.ndarray,
        sample_rate: int,
        start_time: float,
        end_time: float,
    ) -> np.ndarray:
        start_index = int(max(0.0, start_time) * sample_rate)
        end_index = int(max(start_time + 0.1, end_time) * sample_rate)
        padding = int(SNIPPET_PADDING_SECONDS * sample_rate)
        start_index = max(0, start_index - padding)
        end_index = min(len(audio), end_index + padding)
        snippet = audio[start_index:end_index]
        if snippet.size == 0:
            return np.zeros(int(0.25 * sample_rate), dtype=np.float32)
        return snippet.astype(np.float32, copy=False)

    def _snippet_energy(self, snippet: np.ndarray) -> float:
        if snippet.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(snippet), dtype=np.float32)))

    def _build_centroids(self, embeddings: np.ndarray, label_ids: np.ndarray) -> np.ndarray:
        if len(embeddings) == 0:
            raise ValueError("No embeddings were available for centroid construction.")
        if len(label_ids) == 0:
            return embeddings[:1]
        centroids: list[np.ndarray] = []
        for label_id in sorted(set(label_ids.tolist())):
            group = embeddings[label_ids == label_id]
            centroid = group.mean(axis=0)
            centroids.append(normalize_embeddings(np.expand_dims(centroid, axis=0))[0])
        return np.vstack(centroids)

    def _assign_to_centroids(self, embeddings: np.ndarray, centroids: np.ndarray) -> list[int]:
        if len(centroids) == 1:
            return [0] * len(embeddings)
        assignments: list[int] = []
        for embedding in embeddings:
            similarities = centroids @ embedding
            assignments.append(int(np.argmax(similarities)))
        return assignments

    def _assign_segments_to_centroids(
        self,
        snippets: list[np.ndarray],
        transcript: TranscriptResult,
        centroids: np.ndarray,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[int]:
        if len(centroids) == 1:
            return [0] * len(snippets)
        assignments: list[int | None] = []
        total_segments = max(1, len(snippets))
        for index, snippet in enumerate(snippets):
            segment = transcript.segments[index]
            energy = self._snippet_energy(snippet)
            if (
                energy < MIN_STABLE_SEGMENT_ENERGY * ASSIGNMENT_ENERGY_FACTOR
                or segment.duration < MIN_ASSIGNMENT_SEGMENT_DURATION
            ):
                assignments.append(None)
                continue
            if progress_callback is not None and (
                index == 0 or (index + 1) == len(snippets) or (index + 1) % max(1, total_segments // 6) == 0
            ):
                progress_callback(f"Speaker grouping progress: assigning segment {index + 1}/{len(snippets)}.")
            try:
                embedding = normalize_embeddings(
                    np.expand_dims(self.embedding_backend.extract_embedding(snippet, progress_callback), axis=0)
                )[0]
            except Exception:
                assignments.append(None)
                if progress_callback is not None:
                    progress_callback(f"Skipping one assignment snippet at segment {index + 1} because embedding extraction failed.")
                continue
            similarities = centroids @ embedding
            assignments.append(int(np.argmax(similarities)))
        return self._fill_missing_assignments(assignments)

    def _fill_missing_assignments(self, assignments: list[int | None]) -> list[int]:
        if not assignments:
            return []
        first_known = next((label for label in assignments if label is not None), 0)
        resolved: list[int] = [first_known if label is None else label for label in assignments]
        for index, label in enumerate(assignments):
            if label is not None:
                resolved[index] = label
                continue
            previous_label = next((resolved[cursor] for cursor in range(index - 1, -1, -1)), None)
            next_label = next(
                (int(assignments[cursor]) for cursor in range(index + 1, len(assignments)) if assignments[cursor] is not None),
                None,
            )
            if previous_label is not None and next_label is not None and previous_label == next_label:
                resolved[index] = previous_label
            elif previous_label is not None:
                resolved[index] = previous_label
            elif next_label is not None:
                resolved[index] = next_label
            else:
                resolved[index] = first_known
        return resolved

    def _smooth_temporal_islands(self, label_ids: list[int], transcript: TranscriptResult) -> list[int]:
        if len(label_ids) < 3:
            return label_ids
        smoothed = list(label_ids)
        for _ in range(2):
            for index in range(1, len(smoothed) - 1):
                previous_label = smoothed[index - 1]
                current_label = smoothed[index]
                next_label = smoothed[index + 1]
                segment = transcript.segments[index]
                previous_gap = max(0.0, segment.start - transcript.segments[index - 1].end)
                next_gap = max(0.0, transcript.segments[index + 1].start - segment.end)
                if (
                    previous_label == next_label
                    and current_label != previous_label
                    and segment.duration <= MAX_SINGLETON_SEGMENT_DURATION
                    and previous_gap <= MAX_SMOOTHING_GAP
                    and next_gap <= MAX_SMOOTHING_GAP
                ):
                    smoothed[index] = previous_label
            for index in range(1, len(smoothed) - 2):
                outer_label = smoothed[index - 1]
                if (
                    outer_label == smoothed[index + 2]
                    and smoothed[index] != outer_label
                    and smoothed[index + 1] != outer_label
                    and transcript.segments[index].duration <= MAX_SINGLETON_SEGMENT_DURATION
                    and transcript.segments[index + 1].duration <= MAX_SINGLETON_SEGMENT_DURATION
                ):
                    smoothed[index] = outer_label
                    smoothed[index + 1] = outer_label
        return smoothed

    def _format_labels(self, label_ids: list[int]) -> list[str]:
        mapping: dict[int, str] = {}
        labels: list[str] = []
        for label_id in label_ids:
            if label_id not in mapping:
                mapping[label_id] = SPEAKER_LABEL_TEMPLATE.format(index=len(mapping))
            labels.append(mapping[label_id])
        return labels
