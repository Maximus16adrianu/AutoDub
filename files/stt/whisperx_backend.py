"""WhisperX runtime wrapper."""

from __future__ import annotations

import contextlib
import fnmatch
import io
import json
from pathlib import Path
from typing import Callable, Iterator

import numpy as np
import requests
import soundfile as sf
import torch

from files.constants import DEFAULT_WHISPERX_MODEL, WHISPERX_MODEL_PRESETS
from files.stt.language_detection import resolve_source_language
from files.stt.segment_builder import build_transcript_result


class WhisperXBackend:
    MODEL_FILE_PATTERNS = (
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    )

    def __init__(self, models_root: Path, preferred_device: str = "auto") -> None:
        self.models_root = models_root / "whisperx"
        self.models_root.mkdir(parents=True, exist_ok=True)
        self.preferred_device = preferred_device

    def _module(self):  # type: ignore[no-untyped-def]
        import whisperx

        return whisperx

    def _device(self) -> str:
        if self.preferred_device == "cpu":
            return "cpu"
        if self.preferred_device == "cuda" and torch.cuda.is_available():
            return "cuda"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def available(self) -> bool:
        try:
            self._module()
        except Exception:
            return False
        return True

    def _marker_path(self) -> Path:
        return self.models_root / "model-ready.json"

    def prepared_model_info(self) -> dict[str, str] | None:
        marker_path = self._marker_path()
        if not marker_path.exists():
            return None
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        model_name = str(payload.get("model_name") or "").strip()
        if model_name not in WHISPERX_MODEL_PRESETS:
            return None
        return {
            "model_name": model_name,
            "device": str(payload.get("device") or "").strip(),
        }

    def prepared_model_name(self) -> str | None:
        prepared = self.prepared_model_info()
        return prepared["model_name"] if prepared else None

    def active_model_name(self) -> str:
        return self.prepared_model_name() or DEFAULT_WHISPERX_MODEL

    def _normalize_model_name(self, model_name: str | None) -> str:
        resolved = (model_name or "").strip() or self.active_model_name()
        if resolved not in WHISPERX_MODEL_PRESETS:
            supported = ", ".join(WHISPERX_MODEL_PRESETS)
            raise ValueError(f"Unsupported WhisperX model '{resolved}'. Supported values: {supported}")
        return resolved

    def _model_dir(self, model_name: str) -> Path:
        return self.models_root / model_name

    def _local_model_ready(self, model_name: str) -> bool:
        model_dir = self._model_dir(model_name)
        if not model_dir.exists():
            return False
        return all(any(model_dir.glob(pattern)) for pattern in self.MODEL_FILE_PATTERNS)

    def _model_reference(self, model_name: str) -> str:
        if self._local_model_ready(model_name):
            return str(self._model_dir(model_name))
        return model_name

    def _matching_model_files(self, repo_files: list[object]) -> list[tuple[str, int]]:
        matched: list[tuple[str, int]] = []
        for sibling in repo_files:
            filename = str(getattr(sibling, "rfilename", "") or "")
            if not filename:
                continue
            if any(fnmatch.fnmatch(filename, pattern) for pattern in self.MODEL_FILE_PATTERNS):
                size = int(getattr(sibling, "size", 0) or 0)
                matched.append((filename, size))
        return matched

    def _download_model_files(
        self,
        model_name: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> Path:
        model_dir = self._model_dir(model_name)
        model_dir.mkdir(parents=True, exist_ok=True)
        if self._local_model_ready(model_name):
            if progress_callback is not None:
                progress_callback(f"WhisperX {model_name} model files are already present locally.")
            return model_dir

        from huggingface_hub import HfApi, hf_hub_url

        preset = WHISPERX_MODEL_PRESETS[model_name]
        if progress_callback is not None:
            progress_callback(f"Resolving WhisperX files for {preset.display_name} from {preset.repo_id}...")
        model_info = HfApi().model_info(preset.repo_id, files_metadata=True)
        model_files = self._matching_model_files(model_info.siblings)
        if not model_files:
            raise RuntimeError(f"No downloadable files were found for WhisperX model {model_name}.")

        total_bytes = sum(max(size, 0) for _, size in model_files)
        downloaded_total = 0
        last_reported_percent = -1

        for filename, expected_size in model_files:
            target_path = model_dir / filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists() and (expected_size <= 0 or target_path.stat().st_size == expected_size):
                downloaded_total += max(expected_size, target_path.stat().st_size)
                continue
            part_path = target_path.with_suffix(target_path.suffix + ".part")
            part_path.unlink(missing_ok=True)
            file_url = hf_hub_url(preset.repo_id, filename, revision=model_info.sha)
            if progress_callback is not None:
                progress_callback(f"Downloading WhisperX file {filename}...")
            with requests.get(file_url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with part_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded_total += len(chunk)
                        if total_bytes <= 0:
                            continue
                        percent = int(downloaded_total / total_bytes * 100)
                        if percent <= last_reported_percent and downloaded_total < total_bytes:
                            continue
                        last_reported_percent = percent
                        if progress_callback is not None:
                            downloaded_mb = downloaded_total / (1024 * 1024)
                            total_mb = total_bytes / (1024 * 1024)
                            progress_callback(
                                f"WhisperX {model_name}: {percent:.0f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB) | {filename}"
                            )
            part_path.replace(target_path)

        if progress_callback is not None:
            progress_callback(f"WhisperX {model_name} files downloaded. Opening the model to validate the local install...")
        return model_dir

    @contextlib.contextmanager
    def _suppress_library_console_output(self) -> Iterator[None]:
        # `start.pyw` runs without a real console on Windows. Some third-party
        # loaders still write directly to stdout/stderr during model setup.
        # Redirecting both streams here prevents `OSError: [Errno 22] Invalid argument`
        # from torch.hub / Silero under pythonw.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield

    def prepare_model(
        self,
        model_name: str = DEFAULT_WHISPERX_MODEL,
        progress_callback: Callable[[str], None] | None = None,
    ) -> Path:
        whisperx = self._module()
        resolved_model = self._normalize_model_name(model_name)
        model_reference = self._download_model_files(resolved_model, progress_callback)
        device = self._device()
        compute_type = "float16" if device == "cuda" else "int8"
        if progress_callback is not None:
            progress_callback("Initializing WhisperX with the downloaded model files...")
        with self._suppress_library_console_output():
            whisperx.load_model(
                str(model_reference),
                device=device,
                compute_type=compute_type,
                download_root=str(self.models_root),
                vad_method="silero",
            )
        marker_path = self._marker_path()
        marker_path.write_text(
            json.dumps({"model_name": resolved_model, "device": device, "model_dir": str(model_reference)}, indent=2),
            encoding="utf-8",
        )
        return marker_path

    def _load_prepared_audio(self, audio_path: Path, sample_rate: int = 16_000) -> np.ndarray:
        waveform, source_rate = sf.read(str(audio_path), dtype="float32", always_2d=False)
        if isinstance(waveform, np.ndarray) and waveform.ndim > 1:
            waveform = waveform.mean(axis=1)
        waveform = np.asarray(waveform, dtype=np.float32).flatten()
        if source_rate == sample_rate:
            return waveform
        if waveform.size == 0:
            return waveform
        duration = waveform.size / float(source_rate)
        target_samples = max(1, int(round(duration * sample_rate)))
        source_axis = np.linspace(0.0, duration, num=waveform.size, endpoint=False)
        target_axis = np.linspace(0.0, duration, num=target_samples, endpoint=False)
        return np.interp(target_axis, source_axis, waveform).astype(np.float32)

    def transcribe(self, audio_path: Path, source_language: str = "auto", model_name: str | None = None):
        whisperx = self._module()
        resolved_model = self._normalize_model_name(model_name)
        device = self._device()
        compute_type = "float16" if device == "cuda" else "int8"
        with self._suppress_library_console_output():
            model = whisperx.load_model(
                self._model_reference(resolved_model),
                device=device,
                compute_type=compute_type,
                download_root=str(self.models_root),
                vad_method="silero",
            )
            audio = self._load_prepared_audio(audio_path)
            requested_language = None if source_language == "auto" else source_language
            transcription = model.transcribe(audio, batch_size=4, language=requested_language)
            detected_language = resolve_source_language(source_language, transcription.get("language"))
            align_model, metadata = whisperx.load_align_model(language_code=detected_language, device=device)
            aligned = whisperx.align(
                transcription["segments"],
                align_model,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
        return build_transcript_result(aligned["segments"], detected_language)
