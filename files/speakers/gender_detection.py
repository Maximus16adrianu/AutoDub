"""audEERING age/gender speaker classification backend."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import numpy as np
import requests
import soundfile as sf

from files.stt.schemas import TranscriptResult
from files.utils.file_utils import ensure_directory


SpeakerGender = Literal["male", "female", "unknown"]
ProgressCallback = Callable[[str], None] | None

AUDEERING_GENDER_MODEL_URL = (
    "https://zenodo.org/record/7761387/files/w2v2-L-robust-24-age-gender.728d5a4c-1.1.1.zip"
)
MODEL_ARCHIVE_NAME = "audeering_w2v2_age_gender.zip"
MIN_SEGMENT_DURATION_SECONDS = 0.60
MAX_SEGMENT_DURATION_SECONDS = 6.00
MAX_SNIPPETS_PER_SPEAKER = 4
MIN_CONFIDENCE = 0.55
CHILD_CONFIDENCE_BLOCK = 0.45
FEMALE_INDEX = 0
MALE_INDEX = 1
CHILD_INDEX = 2


@dataclass(frozen=True)
class SpeakerGenderGuess:
    speaker_label: str
    gender: SpeakerGender
    female_score: float
    male_score: float
    child_score: float
    confidence: float
    analyzed_snippets: int
    total_segments: int

    def to_dict(self) -> dict[str, object]:
        return {
            "speaker_label": self.speaker_label,
            "gender": self.gender,
            "female_score": self.female_score,
            "male_score": self.male_score,
            "child_score": self.child_score,
            "confidence": self.confidence,
            "analyzed_snippets": self.analyzed_snippets,
            "total_segments": self.total_segments,
        }


class SpeakerGenderDetector:
    def __init__(self, models_root: Path) -> None:
        self.models_root = models_root
        self.asset_dir = models_root / "speaker_gender"
        self.downloads_dir = models_root / "_speaker_gender_downloads"
        self.marker_path = self.asset_dir / "asset-ready.json"
        self._model = None
        self._loaded_root: Path | None = None

    def available(self) -> bool:
        return importlib.util.find_spec("audonnx") is not None and importlib.util.find_spec("onnxruntime") is not None

    def asset_ready(self) -> bool:
        model_root = self.model_root()
        return model_root is not None and any(model_root.glob("*.onnx"))

    def prepare_model(self, progress_callback: ProgressCallback = None) -> Path:
        if not self.available():
            raise RuntimeError("audonnx and onnxruntime are required for audEERING speaker gender detection.")
        ensure_directory(self.asset_dir)
        ensure_directory(self.downloads_dir)
        archive_path = self.downloads_dir / MODEL_ARCHIVE_NAME
        self._download_file(AUDEERING_GENDER_MODEL_URL, archive_path, progress_callback)
        if progress_callback is not None:
            progress_callback("Extracting audEERING speaker gender model...")
        for item in self.asset_dir.iterdir():
            if item == self.marker_path:
                continue
            if item.is_dir():
                import shutil

                shutil.rmtree(item, ignore_errors=True)
            elif item.is_file():
                item.unlink(missing_ok=True)
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(self.asset_dir)
        model_root = self._detect_model_root()
        if model_root is None:
            raise RuntimeError("The audEERING speaker gender model archive was extracted, but no ONNX model files were found.")
        self.marker_path.write_text(json.dumps({"model_root": str(model_root)}, indent=2), encoding="utf-8")
        self._loaded_root = None
        self._model = None
        return model_root

    def model_root(self) -> Path | None:
        if self.marker_path.exists():
            try:
                data = json.loads(self.marker_path.read_text(encoding="utf-8"))
                marker_root = Path(data.get("model_root", ""))
                if marker_root.exists() and any(marker_root.glob("*.onnx")):
                    return marker_root
            except Exception:
                pass
        detected = self._detect_model_root()
        if detected is not None:
            return detected
        return None

    def estimate(
        self,
        audio_path: Path,
        transcript: TranscriptResult,
        progress_callback: ProgressCallback = None,
    ) -> dict[str, SpeakerGenderGuess]:
        labeled_segments = [segment for segment in transcript.segments if segment.speaker]
        if not labeled_segments:
            return {}
        model = self._load_model()
        audio, sample_rate = sf.read(str(audio_path), dtype="float32")
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        grouped_segments: dict[str, list[tuple[float, float]]] = {}
        for segment in labeled_segments:
            grouped_segments.setdefault(segment.speaker or "UNKNOWN", []).append((segment.start, segment.end))
        guesses: dict[str, SpeakerGenderGuess] = {}
        total_speakers = max(1, len(grouped_segments))
        for index, speaker_label in enumerate(sorted(grouped_segments)):
            if progress_callback is not None:
                progress_callback(
                    f"audEERING gender detection: analyzing speaker {index + 1}/{total_speakers} ({speaker_label})."
                )
            segments = grouped_segments[speaker_label]
            snippets = self._collect_snippets(audio, sample_rate, segments)
            probabilities: list[np.ndarray] = []
            for snippet in snippets:
                outputs = model(snippet, sample_rate)
                logits = np.asarray(outputs["logits_gender"], dtype=np.float32).reshape(-1)
                probabilities.append(self._softmax(logits))
            if probabilities:
                mean_probabilities = np.mean(np.vstack(probabilities), axis=0)
            else:
                mean_probabilities = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            female_score = float(mean_probabilities[FEMALE_INDEX])
            male_score = float(mean_probabilities[MALE_INDEX])
            child_score = float(mean_probabilities[CHILD_INDEX])
            top_confidence = max(female_score, male_score)
            if child_score >= CHILD_CONFIDENCE_BLOCK or top_confidence < MIN_CONFIDENCE:
                gender: SpeakerGender = "unknown"
            else:
                gender = "female" if female_score >= male_score else "male"
            guesses[speaker_label] = SpeakerGenderGuess(
                speaker_label=speaker_label,
                gender=gender,
                female_score=female_score,
                male_score=male_score,
                child_score=child_score,
                confidence=top_confidence,
                analyzed_snippets=len(probabilities),
                total_segments=len(segments),
            )
        return guesses

    def _load_model(self):
        model_root = self.model_root()
        if model_root is None:
            raise RuntimeError("The audEERING speaker gender model is not prepared yet.")
        if self._model is not None and self._loaded_root == model_root:
            return self._model
        import audonnx

        self._model = audonnx.load(str(model_root))
        self._loaded_root = model_root
        return self._model

    def _detect_model_root(self) -> Path | None:
        if not self.asset_dir.exists():
            return None
        direct = next(self.asset_dir.glob("*.onnx"), None)
        if direct is not None:
            return self.asset_dir
        nested = next(self.asset_dir.rglob("*.onnx"), None)
        if nested is not None:
            return nested.parent
        return None

    def _collect_snippets(
        self,
        audio: np.ndarray,
        sample_rate: int,
        segments: list[tuple[float, float]],
    ) -> list[np.ndarray]:
        snippets: list[np.ndarray] = []
        scored_segments = sorted(segments, key=lambda item: item[1] - item[0], reverse=True)
        for start_time, end_time in scored_segments:
            duration = max(0.0, end_time - start_time)
            if duration < MIN_SEGMENT_DURATION_SECONDS:
                continue
            if duration > MAX_SEGMENT_DURATION_SECONDS:
                center = start_time + duration / 2.0
                half = MAX_SEGMENT_DURATION_SECONDS / 2.0
                start_time = max(0.0, center - half)
                end_time = center + half
            start_index = max(0, int(start_time * sample_rate))
            end_index = min(len(audio), int(end_time * sample_rate))
            if end_index <= start_index:
                continue
            snippet = audio[start_index:end_index].astype(np.float32, copy=False)
            if snippet.size == 0:
                continue
            snippets.append(snippet)
            if len(snippets) >= MAX_SNIPPETS_PER_SPEAKER:
                break
        return snippets

    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        shifted = logits - np.max(logits)
        exp_values = np.exp(shifted, dtype=np.float32)
        return exp_values / np.sum(exp_values, dtype=np.float32)

    def _download_file(self, url: str, destination: Path, progress_callback: ProgressCallback = None) -> Path:
        ensure_directory(destination.parent)
        if progress_callback is not None:
            progress_callback("Downloading audEERING age/gender model (24-layer)...")
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            total_bytes = int(response.headers.get("Content-Length", "0"))
            downloaded = 0
            last_reported_percent = -1
            with destination.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes and progress_callback is not None:
                        percent = int(downloaded / total_bytes * 100)
                        if percent > last_reported_percent or downloaded >= total_bytes:
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_bytes / (1024 * 1024)
                            progress_callback(f"{destination.name}: {percent:.0f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)")
                            last_reported_percent = percent
        return destination
