"""Timeline rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class TimelineClip:
    path: Path
    start: float
    end: float


@dataclass(frozen=True)
class SpeechPlacement:
    segment_id: str
    path: Path
    source_start: float
    source_end: float


@dataclass(frozen=True)
class RetimedSegment:
    source_start: float
    source_end: float
    output_start: float
    output_end: float
    speech: bool
    segment_id: str | None = None

    @property
    def source_duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)

    @property
    def output_duration(self) -> float:
        return max(0.0, self.output_end - self.output_start)


def _resample_audio(audio: np.ndarray, current_rate: int, target_rate: int) -> np.ndarray:
    if current_rate == target_rate:
        return audio.astype(np.float32)
    if audio.ndim == 1:
        ratio = target_rate / current_rate
        source_positions = np.arange(len(audio), dtype=np.float32)
        target_positions = np.arange(0, len(audio), 1 / ratio, dtype=np.float32)
        return np.interp(target_positions, source_positions, audio).astype(np.float32)
    channels = [_resample_audio(audio[:, channel], current_rate, target_rate) for channel in range(audio.shape[1])]
    min_frames = min(len(channel) for channel in channels)
    return np.stack([channel[:min_frames] for channel in channels], axis=1).astype(np.float32)


def _resample_to_frames(audio: np.ndarray, target_frames: int) -> np.ndarray:
    if target_frames <= 0:
        return np.zeros((0,), dtype=np.float32) if audio.ndim == 1 else np.zeros((0, audio.shape[1]), dtype=np.float32)
    if audio.shape[0] == target_frames:
        return audio.astype(np.float32)
    if audio.shape[0] <= 1:
        if audio.ndim == 1:
            return np.repeat(audio.astype(np.float32), target_frames)
        return np.repeat(audio.astype(np.float32), target_frames, axis=0)
    if audio.ndim == 1:
        source_positions = np.linspace(0, audio.shape[0] - 1, num=audio.shape[0], dtype=np.float32)
        target_positions = np.linspace(0, audio.shape[0] - 1, num=target_frames, dtype=np.float32)
        return np.interp(target_positions, source_positions, audio).astype(np.float32)
    channels = [_resample_to_frames(audio[:, channel], target_frames) for channel in range(audio.shape[1])]
    return np.stack(channels, axis=1).astype(np.float32)


def _apply_fade(audio: np.ndarray, sample_rate: int, fade_ms: float = 12.0) -> np.ndarray:
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


def _apply_fade_multichannel(audio: np.ndarray, sample_rate: int, fade_ms: float = 8.0) -> np.ndarray:
    if audio.size == 0:
        return audio
    if audio.ndim == 1:
        return _apply_fade(audio, sample_rate, fade_ms)
    fade_frames = min(audio.shape[0] // 2, max(1, int(sample_rate * fade_ms / 1000.0)))
    if fade_frames <= 1:
        return audio
    ramp = np.linspace(0.0, 1.0, fade_frames, dtype=np.float32)[:, None]
    audio = audio.copy()
    audio[:fade_frames] *= ramp
    audio[-fade_frames:] *= ramp[::-1]
    return audio


def audio_duration_seconds(path: Path) -> float:
    info = sf.info(str(path))
    if not info.samplerate:
        return 0.0
    return float(info.frames) / float(info.samplerate)


def build_retime_plan(
    speech_placements: list[SpeechPlacement],
    total_source_duration: float,
    *,
    retime_to_dub: bool = True,
) -> tuple[list[TimelineClip], list[RetimedSegment], dict[str, tuple[float, float]], float]:
    placements = sorted(speech_placements, key=lambda item: item.source_start)
    dub_clips: list[TimelineClip] = []
    retimed_segments: list[RetimedSegment] = []
    adjusted_segment_times: dict[str, tuple[float, float]] = {}
    source_cursor = 0.0
    output_cursor = 0.0

    for placement in placements:
        if placement.source_start > source_cursor:
            gap_duration = placement.source_start - source_cursor
            gap_output_start = output_cursor if retime_to_dub else source_cursor
            gap_output_end = gap_output_start + gap_duration
            retimed_segments.append(
                RetimedSegment(
                    source_start=source_cursor,
                    source_end=placement.source_start,
                    output_start=gap_output_start,
                    output_end=gap_output_end,
                    speech=False,
                )
            )
            output_cursor = gap_output_end if retime_to_dub else placement.source_start
        clip_duration = audio_duration_seconds(placement.path)
        segment_output_start = output_cursor if retime_to_dub else placement.source_start
        segment_output_end = (segment_output_start + clip_duration) if retime_to_dub else placement.source_end
        retimed_segments.append(
            RetimedSegment(
                source_start=placement.source_start,
                source_end=placement.source_end,
                output_start=segment_output_start,
                output_end=segment_output_end,
                speech=True,
                segment_id=placement.segment_id,
            )
        )
        dub_clips.append(
            TimelineClip(
                path=placement.path,
                start=segment_output_start,
                end=segment_output_start + clip_duration,
            )
        )
        adjusted_segment_times[placement.segment_id] = (segment_output_start, segment_output_start + clip_duration)
        output_cursor = segment_output_end if retime_to_dub else placement.source_end
        source_cursor = placement.source_end

    if total_source_duration > source_cursor:
        gap_duration = total_source_duration - source_cursor
        gap_output_start = output_cursor if retime_to_dub else source_cursor
        gap_output_end = gap_output_start + gap_duration
        retimed_segments.append(
            RetimedSegment(
                source_start=source_cursor,
                source_end=total_source_duration,
                output_start=gap_output_start,
                output_end=gap_output_end,
                speech=False,
            )
        )
        output_cursor = gap_output_end if retime_to_dub else total_source_duration

    return dub_clips, retimed_segments, adjusted_segment_times, output_cursor


def _build_envelope(
    total_frames: int,
    windows: list[tuple[float, float]],
    sample_rate: int,
    target_gain: float,
    fade_ms: float = 40.0,
) -> np.ndarray:
    envelope = np.ones(total_frames, dtype=np.float32)
    fade_frames = max(1, int(sample_rate * fade_ms / 1000.0))
    for start, end in windows:
        start_index = max(0, int(start * sample_rate))
        end_index = min(total_frames, int(end * sample_rate))
        if end_index <= start_index:
            continue
        envelope[start_index:end_index] = np.minimum(envelope[start_index:end_index], target_gain)
        fade_in_start = max(0, start_index - fade_frames)
        if start_index > fade_in_start:
            ramp = np.linspace(1.0, target_gain, start_index - fade_in_start, dtype=np.float32)
            envelope[fade_in_start:start_index] = np.minimum(envelope[fade_in_start:start_index], ramp)
        fade_out_end = min(total_frames, end_index + fade_frames)
        if fade_out_end > end_index:
            ramp = np.linspace(target_gain, 1.0, fade_out_end - end_index, dtype=np.float32)
            envelope[end_index:fade_out_end] = np.minimum(envelope[end_index:fade_out_end], ramp)
    return envelope


def render_timeline_mix(
    clips: list[TimelineClip],
    output_path: Path,
    total_duration: float,
    sample_rate: int = 22_050,
) -> Path:
    total_frames = max(1, int(total_duration * sample_rate))
    mix = np.zeros(total_frames, dtype=np.float32)
    for clip in clips:
        audio, clip_rate = sf.read(str(clip.path), dtype="float32")
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        audio = _resample_audio(audio.astype(np.float32), clip_rate, sample_rate)
        audio = _apply_fade(audio.astype(np.float32), sample_rate)
        start_index = int(max(0.0, clip.start) * sample_rate)
        end_index = min(total_frames, start_index + len(audio))
        if end_index <= start_index:
            continue
        mix[start_index:end_index] += audio[: end_index - start_index]
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.98:
        mix /= peak / 0.98
    sf.write(str(output_path), mix, sample_rate)
    return output_path


def build_background_bed(
    source_audio_path: Path,
    speech_windows: list[tuple[float, float]],
    output_path: Path,
    sample_rate: int = 22_050,
    center_gain: float = 0.18,
    mono_gain: float = 0.32,
    bed_gain: float = 0.78,
) -> Path:
    audio, current_rate = sf.read(str(source_audio_path), dtype="float32")
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        audio = audio[:, None]
    audio = _resample_audio(audio, current_rate, sample_rate)
    if audio.ndim == 1:
        audio = audio[:, None]
    total_frames = audio.shape[0]
    center_envelope = _build_envelope(
        total_frames,
        speech_windows,
        sample_rate,
        target_gain=center_gain if audio.shape[1] >= 2 else mono_gain,
    )
    bed_envelope = _build_envelope(total_frames, speech_windows, sample_rate, target_gain=bed_gain)
    if audio.shape[1] >= 2:
        left = audio[:, 0]
        right = audio[:, 1]
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        attenuated_mid = mid * center_envelope
        bed = np.stack([attenuated_mid + side, attenuated_mid - side], axis=1)
    else:
        bed = audio * center_envelope[:, None]
    bed *= bed_envelope[:, None]
    peak = float(np.max(np.abs(bed))) if bed.size else 0.0
    if peak > 0.98:
        bed /= peak / 0.98
    sf.write(str(output_path), bed.astype(np.float32), sample_rate)
    return output_path


def build_retimed_background_bed(
    source_audio_path: Path,
    retimed_segments: list[RetimedSegment],
    output_path: Path,
    sample_rate: int = 22_050,
    speech_center_gain: float = 0.008,
    speech_side_gain: float = 0.86,
    speech_total_gain: float = 0.48,
    mono_speech_gain: float = 0.08,
) -> Path:
    source_audio, current_rate = sf.read(str(source_audio_path), dtype="float32")
    source_audio = np.asarray(source_audio, dtype=np.float32)
    if source_audio.ndim == 1:
        source_audio = source_audio[:, None]
    source_audio = _resample_audio(source_audio, current_rate, sample_rate)
    if source_audio.ndim == 1:
        source_audio = source_audio[:, None]
    total_frames = max(1, int(max((segment.output_end for segment in retimed_segments), default=0.0) * sample_rate))
    rendered = np.zeros((total_frames, source_audio.shape[1]), dtype=np.float32)
    for segment in retimed_segments:
        source_start = max(0, int(segment.source_start * sample_rate))
        source_end = min(source_audio.shape[0], int(segment.source_end * sample_rate))
        output_start = max(0, int(segment.output_start * sample_rate))
        output_end = min(total_frames, int(segment.output_end * sample_rate))
        if source_end <= source_start or output_end <= output_start:
            continue
        chunk = source_audio[source_start:source_end]
        if segment.speech:
            if chunk.shape[1] >= 2:
                left = chunk[:, 0]
                right = chunk[:, 1]
                mid = (left + right) * 0.5
                side = (left - right) * 0.5
                attenuated_mid = mid * speech_center_gain
                chunk = np.stack(
                    [
                        (attenuated_mid + side * speech_side_gain) * speech_total_gain,
                        (attenuated_mid - side * speech_side_gain) * speech_total_gain,
                    ],
                    axis=1,
                )
            else:
                chunk = chunk * mono_speech_gain
        if chunk.shape[0] != (output_end - output_start):
            chunk = _resample_to_frames(chunk, output_end - output_start)
        chunk = _apply_fade_multichannel(np.asarray(chunk, dtype=np.float32), sample_rate)
        rendered[output_start:output_start + chunk.shape[0]] = chunk[: total_frames - output_start]
    peak = float(np.max(np.abs(rendered))) if rendered.size else 0.0
    if peak > 0.98:
        rendered /= peak / 0.98
    sf.write(str(output_path), rendered.astype(np.float32), sample_rate)
    return output_path


def blend_background_and_dub(
    background_audio_path: Path,
    dubbed_audio_path: Path,
    output_path: Path,
    sample_rate: int = 22_050,
    dub_gain: float = 1.28,
) -> Path:
    background, background_rate = sf.read(str(background_audio_path), dtype="float32")
    dub, dub_rate = sf.read(str(dubbed_audio_path), dtype="float32")
    background = np.asarray(background, dtype=np.float32)
    dub = np.asarray(dub, dtype=np.float32)
    if background.ndim == 1:
        background = np.stack([background, background], axis=1)
    background = _resample_audio(background, background_rate, sample_rate)
    if background.ndim == 1:
        background = np.stack([background, background], axis=1)
    if dub.ndim > 1:
        dub = dub.mean(axis=1)
    dub = _resample_audio(dub.astype(np.float32), dub_rate, sample_rate)
    dub = _apply_fade(dub.astype(np.float32), sample_rate)
    dub_stereo = np.stack([dub, dub], axis=1) * dub_gain
    total_frames = max(background.shape[0], dub_stereo.shape[0])
    background_padded = np.pad(background, ((0, total_frames - background.shape[0]), (0, 0)))
    dub_padded = np.pad(dub_stereo, ((0, total_frames - dub_stereo.shape[0]), (0, 0)))
    mix = background_padded + dub_padded
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.98:
        mix /= peak / 0.98
    sf.write(str(output_path), mix.astype(np.float32), sample_rate)
    return output_path
