"""Fixed-stack dubbing pipeline."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from files.constants import LANGUAGE_LABELS, PIPELINE_STAGES
from files.core.exceptions import PipelineStageError
from files.core.result_types import JobRequest, JobResult, OutputArtifactPaths
from files.media.extractor import AudioExtractor
from files.media.ffprobe_service import FFProbeService
from files.media.muxer import MediaMuxer
from files.media.timeline import (
    SpeechPlacement,
    TimelineClip,
    blend_background_and_dub,
    build_retime_plan,
    build_retimed_background_bed,
    render_timeline_mix,
)
from files.setup.model_manager import ModelManager
from files.speakers.speaker_assignment import SpeakerAssignmentService
from files.speakers.voice_mapping import assign_voices_to_speakers
from files.storage.export_store import copy_project_exports
from files.storage.project_store import ProjectLayout, prune_project_artifacts
from files.stt.schemas import TranscriptResult
from files.stt.whisperx_backend import WhisperXBackend
from files.translate.argos_backend import ArgosTranslateBackend
from files.tts.duration_fit import fit_clip_duration
from files.utils.json_utils import make_json_safe
from files.tts.piper_backend import PiperBackend
from files.utils.time_utils import srt_timestamp, utc_now_iso


class Pipeline:
    def __init__(
        self,
        ffprobe_service: FFProbeService,
        extractor: AudioExtractor,
        whisperx_backend: WhisperXBackend,
        translation_backend: ArgosTranslateBackend,
        piper_backend: PiperBackend,
        model_manager: ModelManager,
        speaker_service: SpeakerAssignmentService,
        muxer: MediaMuxer,
        logger: logging.Logger,
    ) -> None:
        self.ffprobe_service = ffprobe_service
        self.extractor = extractor
        self.whisperx_backend = whisperx_backend
        self.translation_backend = translation_backend
        self.piper_backend = piper_backend
        self.model_manager = model_manager
        self.speaker_service = speaker_service
        self.speaker_gender_detector = model_manager.speaker_gender_detector
        self.muxer = muxer
        self.logger = logger

    def run(
        self,
        job_id: str,
        request: JobRequest,
        layout: ProjectLayout,
        emit_stage: Callable[[str, float], None],
        emit_progress: Callable[[str, float, str], None],
        emit_log: Callable[[str], None],
        cancel_event: threading.Event,
    ) -> JobResult:
        warnings: list[str] = []
        probe = None
        transcript = TranscriptResult(source_language="unknown")
        translated_segments: list[dict] = []
        subtitle_segments: list[dict] = []
        speaker_map: dict[str, str] = {}
        speaker_gender_guesses: dict[str, dict[str, object]] = {}
        timeline_clips: list[TimelineClip] = []
        adjusted_segment_times: dict[str, tuple[float, float]] = {}
        subtitle_language_resolved: str | None = None
        speaker_grouping_active = request.speaker_grouping_enabled

        def check_cancelled() -> None:
            if cancel_event.is_set():
                raise PipelineStageError("cancelled", "The job was cancelled.")

        def update(stage: str, progress: float, detail: str) -> None:
            emit_stage(stage, progress)
            emit_progress(stage, progress, detail)
            emit_log(detail)
            self.logger.info("%s | %s", stage, detail)
            check_cancelled()

        try:
            update(PIPELINE_STAGES[0], 0.02, "Preparing project files and metadata.")
            metadata = {
                "job_id": job_id,
                "created_at": utc_now_iso(),
                "request": {
                    "source_video": str(request.source_video),
                    "source_language": request.source_language,
                    "target_language": request.target_language,
                    "subtitles_enabled": request.subtitles_enabled,
                    "subtitle_language": request.subtitle_language,
                    "retime_video_to_dub": request.retime_video_to_dub,
                    "speaker_grouping_enabled": request.speaker_grouping_enabled,
                    "voice_mode": request.voice_mode,
                    "max_speaker_voices": request.max_speaker_voices,
                    "auto_match_speaker_gender": request.auto_match_speaker_gender,
                    "preferred_voice_id": request.preferred_voice_id,
                },
                "stages": list(PIPELINE_STAGES),
                "warnings": warnings,
            }
            layout.metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            update(PIPELINE_STAGES[1], 0.08, "Reading media metadata with ffprobe.")
            probe = self.ffprobe_service.probe(request.source_video)

            update(PIPELINE_STAGES[2], 0.16, "Extracting mono WAV audio for analysis.")
            self.extractor.extract_wav(request.source_video, layout.extracted_audio_file)
            emit_log("Extracting stereo source mix to preserve effects and ambience in the final dub.")
            self.extractor.extract_source_mix(request.source_video, layout.source_mix_file)

            update(PIPELINE_STAGES[3], 0.30, "Running WhisperX transcription.")
            transcript = self.whisperx_backend.transcribe(layout.extracted_audio_file, request.source_language)
            transcript.duration = probe.duration

            update(PIPELINE_STAGES[4], 0.38, "Normalizing aligned word timestamps.")
            layout.words_file.write_text(
                json.dumps([word.to_dict() for word in transcript.words], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            update(PIPELINE_STAGES[5], 0.44, "Building structured transcript segments.")
            layout.transcript_file.write_text(
                json.dumps(transcript.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            if request.speaker_grouping_enabled:
                update(PIPELINE_STAGES[6], 0.52, "Extracting speaker embeddings and clustering.")
                speaker_cap = min(max(2, request.max_speaker_voices + 2), 8)
                emit_log(
                    f"Speaker grouping is enabled. Max speaker voices for this job: {request.max_speaker_voices}."
                )
                if not self.model_manager.is_installed("speechbrain-ecapa"):
                    emit_log("Preparing the local SpeechBrain ECAPA asset before speaker grouping starts.")
                    self.model_manager.install_component("speechbrain-ecapa", emit_log)
                self.logger.info(
                    "Speaker grouping internal detection cap for job %s is %s (voice limit %s).",
                    job_id,
                    speaker_cap,
                    request.max_speaker_voices,
                )
                try:
                    speaker_result = self.speaker_service.assign(
                        layout.extracted_audio_file,
                        transcript,
                        max_speakers_hint=speaker_cap,
                        progress_callback=emit_log,
                    )
                except Exception as speaker_exc:
                    speaker_grouping_active = False
                    warnings.append(f"speaker_grouping_fallback: {speaker_exc}")
                    emit_log(
                        "Speaker grouping failed and will fall back to a single shared voice for this job. "
                        "Check the job log for technical details."
                    )
                    self.logger.warning(
                        "Speaker grouping failed for job %s. Falling back to single voice.",
                        job_id,
                        exc_info=speaker_exc,
                    )
                    if layout.speaker_map_file.exists():
                        layout.speaker_map_file.unlink(missing_ok=True)
                else:
                    emit_log(f"Detected {speaker_result.speaker_count} speaker groups after smoothing.")
                    speaker_map = speaker_result.segment_to_speaker
                    layout.speaker_map_file.write_text(
                        json.dumps(
                            {
                                "segment_to_speaker": speaker_result.segment_to_speaker,
                                "speaker_count": speaker_result.speaker_count,
                                "speaker_gender_guesses": speaker_gender_guesses,
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
            else:
                emit_log("Speaker grouping disabled. Using a single shared voice.")

            update(PIPELINE_STAGES[7], 0.62, "Translating transcript segments with Argos Translate.")
            translated_segments = self.translation_backend.translate_segments(
                transcript.segments,
                transcript.source_language,
                request.target_language,
                progress_callback=emit_log,
            )
            layout.translated_segments_file.write_text(
                json.dumps(translated_segments, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            subtitles_output: Path | None = None
            if request.subtitles_enabled:
                subtitle_language_resolved = self._resolve_subtitle_language(
                    request.subtitle_language,
                    transcript.source_language,
                    request.target_language,
                )
                subtitle_segments = self._build_subtitle_segments(
                    transcript,
                    translated_segments,
                    subtitle_language_resolved,
                    request.target_language,
                    emit_log,
                )
            else:
                emit_log("Subtitle export disabled for this job.")
                if layout.subtitles_file.exists():
                    layout.subtitles_file.unlink()

            update(PIPELINE_STAGES[8], 0.72, "Generating segment speech with Piper.")
            if request.voice_mode == "per_speaker" and speaker_grouping_active:
                speaker_labels = [segment.speaker or "SPEAKER_00" for segment in transcript.segments]
                unique_speaker_count = len(set(speaker_labels)) or 1
                desired_voice_count = max(1, min(request.max_speaker_voices, unique_speaker_count))
                gender_hints: dict[str, str] = {}
                if request.auto_match_speaker_gender:
                    emit_log(
                        "Gender-aware voice matching is enabled. The app will use the local audEERING age/gender model on each detected speaker."
                    )
                    if not self.model_manager.is_installed("audeering-gender-model"):
                        emit_log("Preparing the local audEERING speaker gender model before voice assignment starts.")
                        self.model_manager.install_component("audeering-gender-model", emit_log)
                    try:
                        gender_results = self.speaker_gender_detector.estimate(
                            layout.extracted_audio_file,
                            transcript,
                            progress_callback=emit_log,
                        )
                    except Exception as gender_exc:
                        warnings.append(f"speaker_gender_matching_fallback: {gender_exc}")
                        emit_log(
                            "Gender-aware voice matching could not classify the detected speakers. Voice assignment will continue without gender hints."
                        )
                        self.logger.warning(
                            "Speaker gender matching failed for job %s. Continuing without gender hints.",
                            job_id,
                            exc_info=gender_exc,
                        )
                    else:
                        for speaker_label, guess in gender_results.items():
                            speaker_gender_guesses[speaker_label] = guess.to_dict()
                            if guess.gender == "unknown":
                                emit_log(
                                    f"Gender guess for {speaker_label}: unknown "
                                    f"(female {guess.female_score:.2f}, male {guess.male_score:.2f}, child {guess.child_score:.2f}). "
                                    "Voice assignment will stay flexible."
                                )
                                continue
                            gender_hints[speaker_label] = guess.gender
                            emit_log(
                                f"Gender guess for {speaker_label}: {guess.gender} "
                                f"(female {guess.female_score:.2f}, male {guess.male_score:.2f}, child {guess.child_score:.2f})."
                            )
                installed_voice_ids = self.model_manager.ensure_voice_pool(
                    request.target_language,
                    desired_voice_count,
                    emit_log,
                    balance_gender=request.auto_match_speaker_gender,
                )
                if not installed_voice_ids:
                    raise PipelineStageError(
                        "generating speech",
                        f"No managed Piper voices are available for {request.target_language}.",
                    )
                if unique_speaker_count > request.max_speaker_voices:
                    emit_log(
                        f"Detected {unique_speaker_count} speakers, but max voices is set to {request.max_speaker_voices}. "
                        "Extra speakers will reuse installed voices."
                    )
                voice_map = assign_voices_to_speakers(
                    speaker_labels,
                    installed_voice_ids,
                    max_voices=request.max_speaker_voices,
                    random_seed=job_id,
                    speaker_gender_hints=gender_hints if request.auto_match_speaker_gender else None,
                )
                if layout.speaker_map_file.exists():
                    layout.speaker_map_file.write_text(
                        json.dumps(
                            {
                                "segment_to_speaker": speaker_map,
                                "speaker_count": len(set(speaker_labels)),
                                "speaker_gender_guesses": speaker_gender_guesses,
                                "voice_map": voice_map,
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
            else:
                if request.voice_mode == "per_speaker" and not speaker_grouping_active:
                    emit_log("Per-speaker voice mode could not stay active for this job. Falling back to a single shared voice.")
                shared_voice = request.preferred_voice_id or self.piper_backend.voice_manager.default_voice_for_language(
                    request.target_language
                )
                voice_map = {"GLOBAL": shared_voice}

            generated_files: list[tuple[Path, Path, float, str]] = []
            total_segments = max(1, len(transcript.segments))
            emit_log(
                f"Piper synthesis started for {len(transcript.segments)} transcript segments. "
                "Longer videos can take a while here; progress will update as each clip finishes."
            )
            for index, segment in enumerate(transcript.segments):
                check_cancelled()
                speaker_label = segment.speaker or "GLOBAL"
                voice_id = voice_map.get(speaker_label) or voice_map.get("GLOBAL")
                if not voice_id:
                    raise PipelineStageError("generating speech", "No Piper voice was available for synthesis.")
                synth_progress = 0.72 + (index / total_segments) * 0.10
                emit_progress(
                    PIPELINE_STAGES[8],
                    synth_progress,
                    f"Generating speech clip {index + 1}/{len(transcript.segments)} with Piper using {voice_id}.",
                )
                raw_clip = layout.generated_tts / f"{index:04d}_{segment.id}_raw.wav"
                final_clip = layout.generated_tts / f"{index:04d}_{segment.id}.wav"
                text = segment.translated_text or segment.text
                self.piper_backend.synthesize(text, voice_id, raw_clip)
                generated_files.append((raw_clip, final_clip, segment.duration, segment.id))
                if index == 0 or (index + 1) % 10 == 0 or (index + 1) == len(transcript.segments):
                    emit_log(f"Piper progress: completed {index + 1}/{len(transcript.segments)} speech clips.")

            if request.retime_video_to_dub:
                update(PIPELINE_STAGES[9], 0.84, "Keeping natural speech timing and retiming the visual timeline to match.")
            else:
                update(PIPELINE_STAGES[9], 0.84, "Keeping the original video speed and placing natural dub clips on the source timeline.")
            speech_placements: list[SpeechPlacement] = []
            for raw_clip, final_clip, target_duration, segment_id in generated_files:
                check_cancelled()
                fit_index = len(speech_placements)
                fit_progress = 0.84 + (fit_index / total_segments) * 0.06
                emit_progress(
                    PIPELINE_STAGES[9],
                    fit_progress,
                    f"Fitting dub clip {fit_index + 1}/{len(generated_files)} back into the source timeline.",
                )
                _, fit_mode = fit_clip_duration(raw_clip, final_clip, target_duration)
                if fit_mode not in {"natural", "padded"}:
                    warnings.append(f"{segment_id}: duration fit used {fit_mode}")
                matching_segment = next(segment for segment in transcript.segments if segment.id == segment_id)
                speech_placements.append(
                    SpeechPlacement(
                        segment_id=segment_id,
                        path=final_clip,
                        source_start=matching_segment.start,
                        source_end=matching_segment.end,
                    )
                )

            source_duration = probe.duration if probe else transcript.duration or 0.0
            timeline_clips, retimed_segments, adjusted_segment_times, total_duration = build_retime_plan(
                speech_placements,
                source_duration,
                retime_to_dub=request.retime_video_to_dub,
            )
            render_timeline_mix(timeline_clips, layout.dub_voice_mix_file, total_duration)
            if request.retime_video_to_dub:
                emit_log("Building a retimed background bed from the original soundtrack and suppressing the original centered speech more aggressively.")
            else:
                emit_log("Building a preserved background bed on the original timeline and suppressing the original centered speech more aggressively.")
            try:
                build_retimed_background_bed(layout.source_mix_file, retimed_segments, layout.background_bed_file)
                blend_background_and_dub(layout.background_bed_file, layout.dub_voice_mix_file, layout.final_mix_file)
                emit_log("Mixed dubbed speech over the preserved original effects and ambience track.")
            except Exception as mix_exc:
                warnings.append(f"background_bed_fallback: {mix_exc}")
                emit_log("Background-preserving mix failed. Falling back to dubbed speech only for the final track.")
                render_timeline_mix(timeline_clips, layout.final_mix_file, total_duration)
            for item in translated_segments:
                segment_id = item.get("id")
                if segment_id in adjusted_segment_times:
                    dubbed_start, dubbed_end = adjusted_segment_times[segment_id]
                    item["dubbed_start"] = dubbed_start
                    item["dubbed_end"] = dubbed_end
            layout.translated_segments_file.write_text(
                json.dumps(translated_segments, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if request.subtitles_enabled:
                layout.subtitles_file.write_text(self._build_srt(subtitle_segments, adjusted_segment_times), encoding="utf-8")
                subtitles_output = layout.subtitles_file
                emit_log("Subtitle SRT prepared and will be burned into the final video export.")

            update(PIPELINE_STAGES[10], 0.92, "Muxing rendered dubbed audio back into the source video.")
            if request.retime_video_to_dub:
                self.muxer.mux_retimed_dubbed_audio(
                    request.source_video,
                    layout.final_mix_file,
                    layout.dubbed_video_file,
                    retimed_segments,
                    subtitles_path=subtitles_output,
                )
            else:
                self.muxer.mux_dubbed_audio(
                    request.source_video,
                    layout.final_mix_file,
                    layout.dubbed_video_file,
                    subtitles_path=subtitles_output,
                )

            update(PIPELINE_STAGES[11], 0.98, "Writing final exports and subtitles.")
            layout.metadata_file.write_text(
                json.dumps(
                    make_json_safe(
                        {
                        **metadata,
                        "completed_at": utc_now_iso(),
                        "probe": asdict(probe) if probe else {},
                        "source_language": transcript.source_language,
                        "warnings": warnings,
                        "voice_map": voice_map,
                        "speaker_gender_guesses": speaker_gender_guesses,
                        "subtitle_language_resolved": subtitle_language_resolved,
                        "subtitles_enabled": request.subtitles_enabled,
                        "subtitles_burned_into_video": bool(subtitles_output),
                        "mix_strategy": "retimed video with background-preserving center attenuation and dubbed voice overlay"
                        if request.retime_video_to_dub
                        else "original video timing with background-preserving center attenuation and dubbed voice overlay",
                        "adjusted_segment_times": adjusted_segment_times,
                        "output_duration": total_duration,
                        "video_retimed_to_dub": request.retime_video_to_dub,
                        }
                    ),
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            export_bundle = copy_project_exports(layout.root, layout.root.parent.parent / "exports")
            emit_log(f"Export bundle copied to {export_bundle.export_folder}")
            removed_artifacts = prune_project_artifacts(layout)
            if removed_artifacts:
                emit_log(
                    f"Cleaned up {len(removed_artifacts)} temporary project artifacts to keep disk usage under control."
                )
        except Exception as exc:
            self.logger.exception("Pipeline failed for job %s.", job_id)
            raise

        return JobResult(
            job_id=job_id,
            request=request,
            transcript=transcript,
            translated_segments=translated_segments,
            output_paths=OutputArtifactPaths(
                project_folder=layout.root,
                dubbed_video=layout.dubbed_video_file,
                transcript_json=layout.transcript_file,
                words_json=layout.words_file,
                translated_segments_json=layout.translated_segments_file,
                subtitles_srt=subtitles_output,
                metadata_json=layout.metadata_file,
                final_mix_wav=layout.final_mix_file if layout.final_mix_file.exists() else None,
                speaker_map_json=layout.speaker_map_file if layout.speaker_map_file.exists() else None,
            ),
            source_language=transcript.source_language,
            speaker_map=speaker_map,
            warnings=warnings,
        )

    def _resolve_subtitle_language(self, configured_language: str, source_language: str, target_language: str) -> str:
        if configured_language == "target":
            return target_language
        if configured_language == "source":
            return source_language
        return configured_language

    def _build_subtitle_segments(
        self,
        transcript: TranscriptResult,
        translated_segments: list[dict],
        subtitle_language: str,
        dub_language: str,
        emit_log: Callable[[str], None],
    ) -> list[dict]:
        if subtitle_language == dub_language:
            emit_log(f"Subtitle language set to {LANGUAGE_LABELS.get(subtitle_language, subtitle_language)}. Reusing the dubbed translation text.")
            return [dict(item) for item in translated_segments]
        if subtitle_language == transcript.source_language:
            emit_log(f"Subtitle language set to {LANGUAGE_LABELS.get(subtitle_language, subtitle_language)}. Using the source transcript text.")
            return [
                {
                    "id": segment.id,
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": segment.speaker,
                    "source_text": segment.text,
                    "translated_text": segment.text,
                    "language": subtitle_language,
                }
                for segment in transcript.segments
            ]
        emit_log(
            f"Generating subtitles in {LANGUAGE_LABELS.get(subtitle_language, subtitle_language)} separately from the dubbed voice track."
        )
        return self.translation_backend.translate_segments(
            transcript.segments,
            transcript.source_language,
            subtitle_language,
            progress_callback=emit_log,
            attach_to_segments=False,
        )

    def _build_srt(self, subtitle_segments: list[dict], adjusted_segment_times: dict[str, tuple[float, float]]) -> str:
        rows: list[str] = []
        for index, segment in enumerate(subtitle_segments, start=1):
            text = str(segment.get("translated_text") or segment.get("source_text") or "").strip()
            segment_id = str(segment.get("id") or "")
            start, end = adjusted_segment_times.get(
                segment_id,
                (float(segment.get("start", 0.0)), float(segment.get("end", 0.0))),
            )
            rows.append(str(index))
            rows.append(f"{srt_timestamp(start)} --> {srt_timestamp(end)}")
            rows.append(text)
            rows.append("")
        return "\n".join(rows)
