"""Local clustering helpers for speaker embeddings."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

from files.constants import SPEAKER_LABEL_TEMPLATE

DEFAULT_MAX_SPEAKERS = 6
MIN_CLUSTER_CONFIDENCE = 0.06


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    if len(embeddings) == 0:
        return embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / np.maximum(norms, 1e-8)


def choose_cluster_labels(embeddings: np.ndarray, max_speakers: int | None = None) -> np.ndarray:
    if len(embeddings) == 0:
        return np.array([], dtype=int)
    if len(embeddings) == 1:
        return np.zeros(1, dtype=int)

    normalized = normalize_embeddings(embeddings)
    cluster_cap = max(2, min(max_speakers or DEFAULT_MAX_SPEAKERS, len(normalized)))

    best_labels = np.zeros(len(normalized), dtype=int)
    best_score = float("-inf")
    for cluster_count in range(2, cluster_cap + 1):
        labels = AgglomerativeClustering(
            n_clusters=cluster_count,
            metric="cosine",
            linkage="average",
        ).fit_predict(normalized)
        if len(set(labels)) < 2:
            continue
        try:
            raw_score = float(silhouette_score(normalized, labels, metric="cosine"))
        except ValueError:
            continue
        cluster_sizes = np.bincount(labels)
        penalty = 0.015 * (cluster_count - 1)
        if int(cluster_sizes.min()) <= 1:
            penalty += 0.05
        elif int(cluster_sizes.min()) <= 2:
            penalty += 0.02
        adjusted_score = raw_score - penalty
        if adjusted_score > best_score:
            best_score = adjusted_score
            best_labels = labels

    if best_score < MIN_CLUSTER_CONFIDENCE:
        return np.zeros(len(normalized), dtype=int)
    return best_labels.astype(int, copy=False)


def cluster_embeddings(embeddings: np.ndarray, max_speakers: int | None = None) -> list[str]:
    labels = choose_cluster_labels(embeddings, max_speakers=max_speakers)
    if len(labels) == 0:
        return []
    unique_labels: dict[int, int] = {}
    speaker_labels: list[str] = []
    for label in labels.tolist():
        if label not in unique_labels:
            unique_labels[label] = len(unique_labels)
        speaker_labels.append(SPEAKER_LABEL_TEMPLATE.format(index=unique_labels[label]))
    return speaker_labels
