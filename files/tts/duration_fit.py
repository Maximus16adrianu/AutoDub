"""TTS clip timing fit helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def _resample_audio(audio: np.ndarray, current_rate: int, target_rate: int) -> np.ndarray:
    if current_rate == target_rate:
        return audio.astype(np.float32)
    ratio = target_rate / current_rate
    source_positions = np.arange(len(audio), dtype=np.float32)
    target_positions = np.arange(0, len(audio), 1 / ratio, dtype=np.float32)
    return np.interp(target_positions, source_positions, audio).astype(np.float32)


def _trim_silence(audio: np.ndarray, sample_rate: int, threshold: float = 0.01, keep_ms: float = 30.0) -> np.ndarray:
    if audio.size == 0:
        return audio
    active = np.flatnonzero(np.abs(audio) >= threshold)
    if active.size == 0:
        return audio
    keep_frames = int(sample_rate * keep_ms / 1000.0)
    start = max(0, int(active[0]) - keep_frames)
    end = min(len(audio), int(active[-1]) + keep_frames + 1)
    return audio[start:end]


def _apply_fades(audio: np.ndarray, sample_rate: int, fade_ms: float = 12.0) -> np.ndarray:
    if audio.size == 0:
        return audio
    fade_frames = min(len(audio) // 2, max(1, int(sample_rate * fade_ms / 1000.0)))
    if fade_frames <= 1:
        return audio
    ramp = np.linspace(0.0, 1.0, fade_frames, dtype=np.float32)
    audio = audio.copy()
    audio[:fade_frames] *= ramp
    audio[-fade_frames:] *= ramp[::-1]
    return audio


def fit_clip_duration(
    input_path: Path,
    output_path: Path,
    target_duration: float,
    sample_rate: int = 22_050,
) -> tuple[Path, str]:
    audio, current_rate = sf.read(str(input_path), dtype="float32")
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    audio = _resample_audio(audio, current_rate, sample_rate)
    audio = _trim_silence(audio, sample_rate)
    target_frames = max(1, int(target_duration * sample_rate))
    # Keep the spoken voice at natural speed. If the clip is only slightly
    # shorter than the original segment, pad with silence instead of retiming.
    if len(audio) < target_frames and (target_frames - len(audio)) <= int(sample_rate * 0.12):
        padded = np.pad(audio, (0, target_frames - len(audio)))
        padded = _apply_fades(padded.astype(np.float32), sample_rate)
        sf.write(str(output_path), padded, sample_rate)
        return output_path, "padded"
    audio = _apply_fades(audio.astype(np.float32), sample_rate)
    sf.write(str(output_path), audio, sample_rate)
    return output_path, "natural"
