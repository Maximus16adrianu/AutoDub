"""Main CustomTkinter application window."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from queue import Queue

import customtkinter as ctk

from files.bootstrap.relaunch import relaunch_startup
from files.constants import (
    APP_NAME,
    DEFAULT_PIPER_VOICE_BY_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_WHISPERX_MODEL,
    SUPPORTED_DUB_LANGUAGE_CODES,
    WHISPERX_MODEL_PRESETS,
)
from files.core.background import BackgroundTaskRunner
from files.core.events import (
    AppEvent,
    BackgroundTaskFailed,
    DownloadProgress,
    InstallFinished,
    InstallStarted,
    JobFailed,
    JobFinished,
    JobLog,
    JobProgress,
    JobStageChanged,
    JobStarted,
    SetupScanFailed,
    SetupStatusChanged,
)
from files.core.job_manager import JobManager
from files.core.pipeline import Pipeline
from files.core.result_types import EnvironmentStatusItem, JobRequest, QueuedJob
from files.gui import dialogs
from files.gui.app_state import AppState
from files.gui.pages.export_page import ExportPage
from files.gui.pages.home_page import HomePage
from files.gui.pages.processing_page import ProcessingPage
from files.gui.pages.settings_page import SettingsPage
from files.gui.pages.setup_page import SetupPage
from files.gui.pages.transcript_page import TranscriptPage
from files.gui.theme import ACCENT_COLOR, PANEL_COLOR, apply_theme, ui_font
from files.media.extractor import AudioExtractor
from files.media.ffmpeg_service import FFmpegService
from files.media.ffprobe_service import FFProbeService
from files.media.muxer import MediaMuxer
from files.setup.ffmpeg_manager import FFmpegManager
from files.setup.model_manifest import default_piper_voice_id
from files.setup.model_manager import ModelManager
from files.setup.package_manager import PythonPackageManager
from files.setup.environment_manager import EnvironmentManager
from files.speakers.speaker_assignment import SpeakerAssignmentService
from files.storage.settings_store import SettingsStore
from files.translate.argos_backend import ArgosTranslateBackend
from files.tts.piper_backend import PiperBackend
from files.tts.voice_registry import all_voices, voices_for_language
from files.utils.file_utils import open_in_explorer
from files.utils.logging_utils import shutdown_logging_handlers
from files.utils.threading_utils import drain_queue
from files.stt.whisperx_backend import WhisperXBackend


class MainWindow(ctk.CTk):
    def __init__(
        self,
        *,
        paths,
        settings_store: SettingsStore,
        ffmpeg_manager: FFmpegManager,
        model_manager: ModelManager,
        environment_manager: EnvironmentManager,
        python_package_manager: PythonPackageManager,
        event_queue: Queue[AppEvent],
        logger: logging.Logger,
    ) -> None:
        settings = settings_store.load()
        if settings.appearance_mode != "dark":
            settings = settings_store.update({"appearance_mode": "dark"})
        normalized_target_language = (
            settings.default_target_language if settings.default_target_language in SUPPORTED_DUB_LANGUAGE_CODES else DEFAULT_TARGET_LANGUAGE
        )
        if normalized_target_language != settings.default_target_language:
            settings = settings_store.update({"default_target_language": normalized_target_language})
        apply_theme("dark")
        super().__init__()
        self.paths = paths
        self.settings_store = settings_store
        self.ffmpeg_manager = ffmpeg_manager
        self.model_manager = model_manager
        self.environment_manager = environment_manager
        self.python_package_manager = python_package_manager
        self.event_queue = event_queue
        self.logger = logger
        self.app_state = AppState(
            settings=settings,
            source_language=settings.default_source_language,
            target_language=normalized_target_language,
            subtitles_enabled=settings.subtitles_enabled,
            subtitle_language=settings.default_subtitle_language,
            retime_video_to_dub=settings.retime_video_to_dub,
            speaker_grouping_enabled=settings.default_voice_mode == "per_speaker",
            voice_mode=settings.default_voice_mode,
            max_speaker_voices=settings.default_max_speaker_voices,
            auto_match_speaker_gender=settings.auto_match_speaker_gender,
        )
        self.task_runner = BackgroundTaskRunner(event_queue, logger)
        self.pipeline: Pipeline | None = None
        self.job_manager: JobManager | None = None
        self._return_page_after_install: str | None = None
        self._pending_job_request: JobRequest | None = None
        self._pending_job_from_queue = False
        self._active_install_title: str | None = None
        self.title(APP_NAME)
        self.geometry("1360x860")
        self.minsize(1080, 700)
        self.configure(fg_color=PANEL_COLOR)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_pages()
        self._rebuild_runtime_services()
        self._load_settings_into_pages()
        self.show_page("Setup")
        self.after(150, self._poll_events)
        self.after(300, self.run_environment_scan)

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color="#10151d")
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_rowconfigure(8, weight=1)
        title = ctk.CTkLabel(self.sidebar, text=APP_NAME, font=ui_font(20, weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=18, pady=(20, 4))
        subtitle = ctk.CTkLabel(self.sidebar, text="Offline dubbing studio", text_color="#91a7c0", font=ui_font(12))
        subtitle.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 20))
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for index, page_name in enumerate(["Setup", "Home", "Processing", "Transcript", "Export", "Settings"], start=2):
            button = ctk.CTkButton(
                self.sidebar,
                text=page_name,
                anchor="w",
                height=34,
                font=ui_font(12),
                fg_color="transparent",
                hover_color="#17212d",
                command=lambda target=page_name: self.show_page(target),
            )
            button.grid(row=index, column=0, sticky="ew", padx=12, pady=3)
            self.nav_buttons[page_name] = button

    def _build_pages(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.pages = {
            "Setup": SetupPage(self.content, self),
            "Home": HomePage(self.content, self),
            "Processing": ProcessingPage(self.content, self),
            "Transcript": TranscriptPage(self.content, self),
            "Export": ExportPage(self.content, self),
            "Settings": SettingsPage(self.content, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()

    def _load_settings_into_pages(self) -> None:
        settings = self.settings_store.load()
        self.app_state.settings = settings
        if settings.last_opened_file:
            from pathlib import Path

            candidate = Path(settings.last_opened_file)
            if candidate.exists():
                self.app_state.selected_file = candidate
        home_page: HomePage = self.pages["Home"]  # type: ignore[assignment]
        normalized_target_language = (
            settings.default_target_language if settings.default_target_language in SUPPORTED_DUB_LANGUAGE_CODES else DEFAULT_TARGET_LANGUAGE
        )
        home_page.apply_settings(
            source_language_label=self._language_label(settings.default_source_language),
            target_language_label=self._language_label(normalized_target_language),
            voice_mode_label="Single voice" if settings.default_voice_mode == "single" else "One voice per detected speaker",
            max_speaker_voices=settings.default_max_speaker_voices,
            auto_match_speaker_gender=settings.auto_match_speaker_gender,
            subtitles_enabled=settings.subtitles_enabled,
            subtitle_language_label=self._subtitle_language_label(settings.default_subtitle_language),
            retime_video_to_dub=settings.retime_video_to_dub,
        )
        home_page.update_selected_file(self.app_state.selected_file)
        home_page.update_queue(self.app_state.queued_jobs, self.app_state.queue_running)
        settings_page: SettingsPage = self.pages["Settings"]  # type: ignore[assignment]
        settings_page.refresh(settings, self.paths, self.model_manager.installed_summary())
        self._refresh_visible_pages()

    def _language_label(self, language_code: str) -> str:
        from files.constants import LANGUAGE_LABELS

        return LANGUAGE_LABELS[language_code]

    def _subtitle_language_label(self, subtitle_language: str) -> str:
        from files.constants import LANGUAGE_LABELS, SUBTITLE_LANGUAGE_LABELS

        if subtitle_language in SUBTITLE_LANGUAGE_LABELS:
            return SUBTITLE_LANGUAGE_LABELS[subtitle_language]
        return LANGUAGE_LABELS.get(subtitle_language, LANGUAGE_LABELS["en"])

    def _rebuild_runtime_services(self) -> None:
        ffmpeg_path = self.ffmpeg_manager.find_ffmpeg()
        ffprobe_path = self.ffmpeg_manager.find_ffprobe()
        ffmpeg_service = FFmpegService(ffmpeg_path)
        ffprobe_service = FFProbeService(ffprobe_path)
        extractor = AudioExtractor(ffmpeg_service)
        muxer = MediaMuxer(ffmpeg_service)
        whisperx_backend: WhisperXBackend = self.model_manager.whisperx_backend
        translation_backend = ArgosTranslateBackend(self.model_manager.argos_manager)
        piper_backend = PiperBackend(self.paths.models, self.model_manager.piper_runtime_dir)
        speaker_service = SpeakerAssignmentService(self.model_manager.speechbrain_backend)
        self.pipeline = Pipeline(
            ffprobe_service=ffprobe_service,
            extractor=extractor,
            whisperx_backend=whisperx_backend,
            translation_backend=translation_backend,
            piper_backend=piper_backend,
            model_manager=self.model_manager,
            speaker_service=speaker_service,
            muxer=muxer,
            logger=self.logger,
        )
        self.job_manager = JobManager(self.paths.projects, self.event_queue, self.pipeline, self.logger)

    def show_page(self, page_name: str) -> None:
        self.app_state.current_page = page_name
        for name, page in self.pages.items():
            if name == page_name:
                page.grid()
                page.tkraise()
            else:
                page.grid_remove()
        self.pages[page_name].focus_set()
        for name, button in self.nav_buttons.items():
            button.configure(fg_color=ACCENT_COLOR if name == page_name else "transparent")
        if page_name == "Transcript":
            self.pages["Transcript"].load_result(self.app_state.latest_result)  # type: ignore[call-arg]
        if page_name == "Export":
            self.pages["Export"].load_result(self.app_state.latest_result)  # type: ignore[call-arg]
        self._refresh_visible_pages()

    def _poll_events(self) -> None:
        drain_queue(self.event_queue, self._handle_event)
        self.after(150, self._poll_events)

    def _handle_event(self, event: AppEvent) -> None:
        if isinstance(event, SetupStatusChanged):
            self.app_state.environment_snapshot = event.snapshot
            self.app_state.installed_components_summary = self.model_manager.installed_summary()
            self.pages["Setup"].refresh_snapshot(event.snapshot)  # type: ignore[call-arg]
            self.pages["Home"]._refresh_voice_options()  # type: ignore[attr-defined]
            self._update_home_readiness()
            self.pages["Settings"].refresh(self.settings_store.load(), self.paths, self.app_state.installed_components_summary)  # type: ignore[call-arg]
            self._refresh_visible_pages()
            return
        if isinstance(event, SetupScanFailed):
            self.pages["Processing"].append_log(event.error)  # type: ignore[call-arg]
            dialogs.show_error(self, "Environment scan failed", event.error)
            return
        if isinstance(event, JobStarted):
            self.app_state.current_job_id = event.job_id
            self._mark_queue_job_started(event.job_id)
            self.pages["Processing"].set_job_started(event.job_id, self._queue_processing_label())  # type: ignore[call-arg]
            self.show_page("Processing")
            self._refresh_visible_pages()
            return
        if isinstance(event, JobStageChanged):
            self.pages["Processing"].update_stage(event.stage, event.stage, event.progress)  # type: ignore[call-arg]
            return
        if isinstance(event, JobLog):
            self.pages["Processing"].append_log(event.message)  # type: ignore[call-arg]
            return
        if isinstance(event, JobProgress):
            self.pages["Processing"].update_stage(event.stage, event.detail, event.progress)  # type: ignore[call-arg]
            return
        if isinstance(event, JobFinished):
            queue_item = self._find_queue_item(job_id=event.job_id)
            if event.job_id != self.app_state.current_job_id and (queue_item is None or queue_item.status != "running"):
                self.logger.warning("Ignoring stale JobFinished event for %s.", event.job_id)
                return
            self.app_state.current_job_id = None
            self.app_state.latest_result = event.result
            was_queued_job = queue_item is not None
            continue_queue = self._handle_queue_job_finished(event.result)
            if continue_queue:
                finish_text = "Queue item finished"
            else:
                finish_text = "Queue complete" if was_queued_job else "Finished"
            self.pages["Processing"].set_finished(finish_text)  # type: ignore[call-arg]
            self.pages["Export"].load_result(event.result)  # type: ignore[call-arg]
            if continue_queue:
                self.pages["Processing"].append_log("Queue advancing to the next item.")  # type: ignore[call-arg]
                self.after(150, self._start_next_queued_job)
                self._refresh_visible_pages()
                return
            self.pages["Processing"].set_queue_text(self._queue_processing_label())  # type: ignore[call-arg]
            self.show_page("Export")
            self._refresh_visible_pages()
            return
        if isinstance(event, JobFailed):
            queue_item = self._find_queue_item(job_id=event.job_id)
            if event.job_id != self.app_state.current_job_id and (queue_item is None or queue_item.status != "running"):
                self.logger.warning("Ignoring stale JobFailed event for %s: %s", event.job_id, event.error)
                return
            self.app_state.current_job_id = None
            was_queued_job = queue_item is not None or self._find_queue_item(self.app_state.active_queue_item_id) is not None
            continue_queue = self._handle_queue_job_failed(event.job_id, event.error)
            if continue_queue:
                failed_text = "Queue item failed"
            elif was_queued_job:
                failed_text = "Queue finished with failures"
            else:
                failed_text = "Failed"
            self.pages["Processing"].set_failed(failed_text)  # type: ignore[call-arg]
            self.pages["Processing"].append_log(event.error)  # type: ignore[call-arg]
            self.pages["Processing"].set_queue_text(self._queue_processing_label())  # type: ignore[call-arg]
            if continue_queue:
                self.pages["Processing"].append_log("Queue will continue with the next item.")  # type: ignore[call-arg]
                self.after(150, self._start_next_queued_job)
                self._refresh_visible_pages()
                return
            if "cancelled" not in event.error.lower() and not self.app_state.queue_running:
                dialogs.show_error(self, "Job failed", event.error)
            self._refresh_visible_pages()
            return
        if isinstance(event, BackgroundTaskFailed):
            self.logger.error("Background task failed: %s | %s", event.task_id, event.error)
            self.pages["Processing"].append_log(f"Background task failed: {event.task_id} - {event.error}")  # type: ignore[call-arg]
            if event.task_id.startswith("install-"):
                self.pages["Processing"].set_failed("Install failed")  # type: ignore[call-arg]
                dialogs.show_error(self, "Install failed", event.error)
            elif event.task_id == "setup-scan":
                dialogs.show_error(self, "Environment scan failed", event.error)
            else:
                dialogs.show_error(self, "Background task failed", event.error)
            return
        if isinstance(event, InstallStarted):
            self._active_install_title = event.title
            self.pages["Processing"].set_install_started(event.title, self._queue_processing_label())  # type: ignore[call-arg]
            self.pages["Processing"].append_log(f"Installing {event.title}...")  # type: ignore[call-arg]
            return
        if isinstance(event, DownloadProgress):
            processing_page: ProcessingPage = self.pages["Processing"]  # type: ignore[assignment]
            install_stage = f"Installing {self._active_install_title}" if self._active_install_title else "Installing component"
            progress_value = event.progress if event.progress > 0 else self._progress_from_text(event.detail)
            if progress_value is None:
                progress_value = processing_page.current_progress()
            processing_page.update_stage(install_stage, event.detail, progress_value)
            self.pages["Processing"].append_log(event.detail)  # type: ignore[call-arg]
            return
        if isinstance(event, InstallFinished):
            self.pages["Processing"].append_log(event.message)  # type: ignore[call-arg]
            self._active_install_title = None
            if event.success:
                self.pages["Processing"].set_finished("Ready")  # type: ignore[call-arg]
                self._rebuild_runtime_services()
                self.run_environment_scan()
                if self._pending_job_request and event.component_id == f"piper-voice-{self._pending_job_request.preferred_voice_id}":
                    request = self._pending_job_request
                    pending_from_queue = self._pending_job_from_queue
                    self._pending_job_request = None
                    self.after(
                        100,
                        lambda queued_request=request, from_queue=pending_from_queue: self._submit_job_request(
                            queued_request,
                            show_dialog_on_error=not from_queue,
                        ),
                    )
                    self._pending_job_from_queue = False
                    return
                if self._return_page_after_install:
                    page_name = self._return_page_after_install
                    self._return_page_after_install = None
                    self.after(100, lambda target_page=page_name: self.show_page(target_page))
            else:
                self.pages["Processing"].set_failed("Install failed")  # type: ignore[call-arg]
                if self._pending_job_request and event.component_id == f"piper-voice-{self._pending_job_request.preferred_voice_id}":
                    if self._pending_job_from_queue:
                        self._mark_active_queue_item_failed(event.message)
                        self._pending_job_from_queue = False
                        self._pending_job_request = None
                        self._refresh_visible_pages()
                        if self.app_state.queue_running:
                            self.pages["Processing"].append_log("Queue voice install failed. Continuing with the next queued item.")  # type: ignore[call-arg]
                            self.after(150, self._start_next_queued_job)
                        return
                    self._pending_job_request = None
                    self._pending_job_from_queue = False
                self._return_page_after_install = None
                dialogs.show_error(self, "Install failed", event.message)
            return

    def _refresh_visible_pages(self) -> None:
        home_page: HomePage = self.pages["Home"]  # type: ignore[assignment]
        home_page.update_selected_file(self.app_state.selected_file)
        home_page._refresh_voice_options()
        home_page.update_queue(self.app_state.queued_jobs, self.app_state.queue_running)
        self._update_home_readiness()
        current_page = self.app_state.current_page
        if current_page == "Transcript":
            self.pages["Transcript"].load_result(self.app_state.latest_result)  # type: ignore[call-arg]
        if current_page == "Export":
            self.pages["Export"].load_result(self.app_state.latest_result)  # type: ignore[call-arg]
        if current_page == "Settings":
            self.pages["Settings"].refresh(  # type: ignore[call-arg]
                self.settings_store.load(),
                self.paths,
                self.model_manager.installed_summary(),
            )

    def run_environment_scan(self) -> None:
        def task() -> None:
            try:
                snapshot = self.environment_manager.summarize_status()
            except Exception as exc:
                self.logger.exception("Environment scan failed.")
                self.event_queue.put(SetupScanFailed(error=str(exc)))
                return
            self.event_queue.put(SetupStatusChanged(snapshot))

        self.task_runner.submit("setup-scan", task)

    def install_all_missing(self) -> None:
        whisperx_model_name: str | None = None
        if not self.model_manager.is_installed("whisperx-default-model"):
            whisperx_model_name = self._prompt_for_whisperx_model()
            if whisperx_model_name is None:
                return

        def task() -> None:
            self.event_queue.put(InstallStarted(component_id="all", title="all missing required components"))
            try:
                if whisperx_model_name:
                    preset = WHISPERX_MODEL_PRESETS[whisperx_model_name]
                    self.event_queue.put(
                        DownloadProgress(
                            component_id="all",
                            progress=0.0,
                            detail=f"WhisperX download choice: {preset.display_name} ({whisperx_model_name}, {preset.size_hint}).",
                        )
                    )
                self.environment_manager.install_all_missing_required(
                    lambda message: self.event_queue.put(DownloadProgress(component_id="all", progress=0.0, detail=message)),
                    whisperx_model_name=whisperx_model_name,
                )
            except Exception as exc:
                self.logger.exception("Install-all flow failed.")
                self.event_queue.put(InstallFinished(component_id="all", success=False, message=str(exc)))
                return
            self.event_queue.put(InstallFinished(component_id="all", success=True, message="Required components installed."))

        self.show_page("Processing")
        self.task_runner.submit("install-all", task)

    def handle_setup_action(self, item: EnvironmentStatusItem, action_name: str) -> None:
        if action_name == "Retry check":
            self.run_environment_scan()
            return
        if action_name == "Open models folder":
            self.open_models_folder()
            return
        if action_name == "Open logs folder":
            self.open_logs_folder()
            return
        if action_name == "Locate FFmpeg":
            selected = dialogs.choose_executable(self, "Locate ffmpeg.exe")
            if selected:
                self.ffmpeg_manager.save_ffmpeg_path(str(selected))
                self._rebuild_runtime_services()
                self.run_environment_scan()
            return
        if action_name == "Locate ffprobe":
            selected = dialogs.choose_executable(self, "Locate ffprobe.exe")
            if selected:
                self.ffmpeg_manager.save_ffprobe_path(str(selected))
                self._rebuild_runtime_services()
                self.run_environment_scan()
            return
        if action_name == "Install FFmpeg automatically":
            self._install_ffmpeg_tools()
            return
        if action_name == "Download/install WhisperX model":
            whisperx_model_name = self._prompt_for_whisperx_model()
            if whisperx_model_name is None:
                return
            preset = WHISPERX_MODEL_PRESETS[whisperx_model_name]
            self._install_component(
                "whisperx-default-model",
                f"WhisperX {preset.display_name}",
                whisperx_model_name=whisperx_model_name,
            )
            return
        if action_name == "Install Piper runtime":
            self._install_piper_runtime()
            return
        if action_name == "Install Piper voice":
            target_language = self.pages["Home"].get_target_language_code()  # type: ignore[call-arg]
            self._install_voice_for_language(target_language)
            return
        if action_name == "Prepare SpeechBrain asset":
            self._install_component("speechbrain-ecapa", "SpeechBrain ECAPA")
            return
        if action_name == "Install audEERING gender model":
            self._install_component("audeering-gender-model", "audEERING speaker gender model")
            return
        if action_name == "Install missing Python dependencies":
            self._install_python_dependencies()
            return
        if action_name == "Install Argos language packages":
            source_language = self.pages["Home"].get_source_language_code()  # type: ignore[call-arg]
            target_language = self.pages["Home"].get_target_language_code()  # type: ignore[call-arg]
            if source_language == "auto":
                source_language = self.settings_store.load().default_source_language
                if source_language == "auto":
                    source_language = "en"
            if source_language == target_language:
                dialogs.show_info(
                    self,
                    "Translation package not needed",
                    "Source and target languages are the same, so no Argos language package is required.",
                )
                return
            self._install_argos_pair(source_language, target_language)

    def _install_component(
        self,
        component_id: str,
        title: str,
        *,
        return_page: str | None = None,
        whisperx_model_name: str | None = None,
    ) -> None:
        self._return_page_after_install = return_page
        def task() -> None:
            self.event_queue.put(InstallStarted(component_id=component_id, title=title))
            try:
                if component_id == "whisperx-default-model" and whisperx_model_name:
                    preset = WHISPERX_MODEL_PRESETS[whisperx_model_name]
                    self.event_queue.put(
                        DownloadProgress(
                            component_id=component_id,
                            progress=0.0,
                            detail=f"WhisperX download choice: {preset.display_name} ({whisperx_model_name}, {preset.size_hint}).",
                        )
                    )
                self.model_manager.install_component(
                    component_id,
                    lambda message: self.event_queue.put(
                        DownloadProgress(component_id=component_id, progress=0.0, detail=message)
                    ),
                    whisperx_model_name=whisperx_model_name,
                )
            except Exception as exc:
                self.logger.exception("Component install failed: %s", component_id)
                self.event_queue.put(InstallFinished(component_id=component_id, success=False, message=str(exc)))
                return
            success_message = f"{title} installed."
            if component_id == "whisperx-default-model" and whisperx_model_name:
                success_message = f"{title} installed and set as the active transcription model."
            self.event_queue.put(InstallFinished(component_id=component_id, success=True, message=success_message))

        self.show_page("Processing")
        self.task_runner.submit(f"install-{component_id}", task)

    def _prompt_for_whisperx_model(self) -> str | None:
        return dialogs.choose_whisperx_model(
            self,
            default_model=DEFAULT_WHISPERX_MODEL,
            prepared_model=self.model_manager.prepared_whisperx_model(),
        )

    def _progress_from_text(self, detail: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d+)?)%", detail)
        if not match:
            return None
        try:
            return max(0.0, min(1.0, float(match.group(1)) / 100.0))
        except ValueError:
            return None

    def _build_job_request_for_source(self, source_video: Path) -> JobRequest:
        self.on_home_settings_changed()
        return JobRequest(
            source_video=source_video,
            source_language=self.app_state.source_language,
            target_language=self.app_state.target_language,
            subtitles_enabled=self.app_state.subtitles_enabled,
            subtitle_language=self.app_state.subtitle_language,
            retime_video_to_dub=self.app_state.retime_video_to_dub,
            speaker_grouping_enabled=self.app_state.speaker_grouping_enabled,
            voice_mode=self.app_state.voice_mode,
            max_speaker_voices=self.app_state.max_speaker_voices,
            auto_match_speaker_gender=self.app_state.auto_match_speaker_gender if self.app_state.voice_mode == "per_speaker" else False,
            preferred_voice_id=self.app_state.preferred_voice_id if self.app_state.voice_mode == "single" else "",
        )

    def _environment_ready_for_jobs(self) -> bool:
        snapshot = self.app_state.environment_snapshot
        return snapshot is not None and snapshot.ready

    def _ensure_request_voice_ready(self, request: JobRequest, *, interactive: bool) -> tuple[bool, str | None]:
        if request.voice_mode != "single" or not request.preferred_voice_id:
            return True, None
        if self.model_manager.voice_manager.voice_installed(request.preferred_voice_id):
            return True, None
        if not self._voice_installable(request.target_language, request.preferred_voice_id):
            return False, "No managed Piper voice download is available for the selected target language."
        if interactive:
            install_now = dialogs.confirm(
                self,
                "Install selected voice",
                "The selected Piper voice is not installed yet. Install it now and continue automatically?",
            )
            if not install_now:
                return False, "Voice installation was cancelled."
        self._pending_job_request = request
        self._pending_job_from_queue = self.app_state.queue_running
        self._install_voice_by_id(request.preferred_voice_id)
        return False, None

    def _find_queue_item(self, queue_id: str | None = None, *, job_id: str | None = None) -> QueuedJob | None:
        if queue_id is not None:
            for item in self.app_state.queued_jobs:
                if item.queue_id == queue_id:
                    return item
        if job_id is not None:
            for item in self.app_state.queued_jobs:
                if item.job_id == job_id:
                    return item
        return None

    def _mark_queue_job_started(self, job_id: str) -> None:
        active_item = self._find_queue_item(self.app_state.active_queue_item_id)
        if active_item is None:
            return
        active_item.status = "running"
        active_item.job_id = job_id

    def _mark_active_queue_item_failed(self, error_message: str) -> None:
        active_item = self._find_queue_item(self.app_state.active_queue_item_id)
        if active_item is None:
            return
        active_item.status = "failed"
        active_item.error_message = error_message
        self.app_state.active_queue_item_id = None

    def _handle_queue_job_finished(self, result) -> bool:  # type: ignore[no-untyped-def]
        queue_item = self._find_queue_item(job_id=result.job_id)
        if queue_item is None:
            self.app_state.queue_running = False
            self.app_state.active_queue_item_id = None
            return False
        queue_item.status = "completed"
        queue_item.result = result
        queue_item.error_message = ""
        self.app_state.active_queue_item_id = None
        if self.app_state.queue_running and any(item.status == "pending" for item in self.app_state.queued_jobs):
            return True
        self.app_state.queue_running = False
        return False

    def _handle_queue_job_failed(self, job_id: str, error_message: str) -> bool:
        queue_item = self._find_queue_item(job_id=job_id) or self._find_queue_item(self.app_state.active_queue_item_id)
        if queue_item is None:
            self.app_state.queue_running = False
            self.app_state.active_queue_item_id = None
            return False
        queue_item.status = "failed"
        queue_item.error_message = error_message
        self.app_state.active_queue_item_id = None
        if self.app_state.queue_running and any(item.status == "pending" for item in self.app_state.queued_jobs):
            return True
        self.app_state.queue_running = False
        return False

    def _queue_processing_label(self) -> str:
        if not self.app_state.queued_jobs:
            return ""
        total = len(self.app_state.queued_jobs)
        completed = sum(1 for item in self.app_state.queued_jobs if item.status == "completed")
        failed = sum(1 for item in self.app_state.queued_jobs if item.status == "failed")
        pending = sum(1 for item in self.app_state.queued_jobs if item.status == "pending")
        active_item = self._find_queue_item(self.app_state.active_queue_item_id)
        if active_item is not None:
            position = self.app_state.queued_jobs.index(active_item) + 1
            return f"Queue {position}/{total} | {pending} pending | {completed} completed | {failed} failed"
        if self.app_state.queue_running:
            return f"Queue active | {pending} pending | {completed} completed | {failed} failed"
        return ""

    def _enqueue_request(self, request: JobRequest) -> None:
        self.app_state.queued_jobs.append(
            QueuedJob(
                queue_id=uuid.uuid4().hex[:8],
                request=request,
                source_name=request.source_video.name,
            )
        )

    def add_videos_to_queue(self) -> None:
        if self.app_state.queue_running:
            return
        selections = dialogs.choose_video_files(self)
        if not selections:
            return
        for selected in selections:
            self._enqueue_request(self._build_job_request_for_source(selected))
        self.app_state.selected_file = selections[-1]
        self.settings_store.update({"last_opened_file": str(selections[-1])})
        self._refresh_visible_pages()

    def remove_queue_item(self, queue_id: str) -> None:
        if self.app_state.queue_running:
            return
        self.app_state.queued_jobs = [item for item in self.app_state.queued_jobs if item.queue_id != queue_id]
        self._refresh_visible_pages()

    def clear_queue(self) -> None:
        if self.app_state.queue_running:
            return
        self.app_state.queued_jobs.clear()
        self.app_state.active_queue_item_id = None
        self._refresh_visible_pages()

    def start_queue(self) -> None:
        processing_page: ProcessingPage = self.pages["Processing"]  # type: ignore[assignment]
        if self.app_state.queue_running or processing_page.status_label.cget("text") in {"Running", "Installing"}:
            dialogs.show_error(self, "Queue busy", "Wait for the current job or install task to finish before starting the queue.")
            return
        if not any(item.status == "pending" for item in self.app_state.queued_jobs):
            dialogs.show_error(self, "Queue empty", "Add at least one pending video to the queue first.")
            return
        if not self._environment_ready_for_jobs():
            dialogs.show_error(self, "Setup incomplete", "Finish the required Setup items before starting the queue.")
            return
        self.app_state.queue_running = True
        self.show_page("Processing")
        self.pages["Processing"].set_queue_text(self._queue_processing_label())  # type: ignore[call-arg]
        self._start_next_queued_job()
        self._refresh_visible_pages()

    def _start_next_queued_job(self) -> None:
        if not self.app_state.queue_running:
            return
        next_item = next((item for item in self.app_state.queued_jobs if item.status == "pending"), None)
        if next_item is None:
            self.app_state.queue_running = False
            self.app_state.active_queue_item_id = None
            self.pages["Processing"].set_finished("Queue complete")  # type: ignore[call-arg]
            self.pages["Processing"].set_queue_text(self._queue_processing_label())  # type: ignore[call-arg]
            self._refresh_visible_pages()
            return
        next_item.status = "running"
        next_item.error_message = ""
        self.app_state.active_queue_item_id = next_item.queue_id
        self.pages["Processing"].append_log(f"Starting queued item: {next_item.source_name}")  # type: ignore[call-arg]
        ready, error_message = self._ensure_request_voice_ready(next_item.request, interactive=False)
        if error_message:
            self._mark_active_queue_item_failed(error_message)
            self.pages["Processing"].append_log(error_message)  # type: ignore[call-arg]
            self.after(100, self._start_next_queued_job)
            self._refresh_visible_pages()
            return
        if not ready:
            self._refresh_visible_pages()
            return
        self._submit_job_request(next_item.request, show_dialog_on_error=False)

    def _install_piper_runtime(self) -> None:
        def task() -> None:
            self.event_queue.put(InstallStarted(component_id="piper-runtime", title="Piper runtime"))
            try:
                self.model_manager.install_piper_runtime(
                    lambda message: self.event_queue.put(
                        DownloadProgress(component_id="piper-runtime", progress=0.0, detail=message)
                    )
                )
            except Exception as exc:
                self.logger.exception("Piper runtime install failed.")
                self.event_queue.put(InstallFinished(component_id="piper-runtime", success=False, message=str(exc)))
                return
            self.event_queue.put(InstallFinished(component_id="piper-runtime", success=True, message="Piper runtime installed."))

        self.show_page("Processing")
        self.task_runner.submit("install-piper-runtime", task)

    def _install_ffmpeg_tools(self) -> None:
        def task() -> None:
            self.event_queue.put(InstallStarted(component_id="ffmpeg-tools", title="FFmpeg tools"))
            try:
                ffmpeg_path, ffprobe_path = self.ffmpeg_manager.install_managed_binaries(
                    lambda message: self.event_queue.put(
                        DownloadProgress(component_id="ffmpeg-tools", progress=0.0, detail=message)
                    )
                )
            except Exception as exc:
                self.logger.exception("FFmpeg install failed.")
                self.event_queue.put(InstallFinished(component_id="ffmpeg-tools", success=False, message=str(exc)))
                return
            self.event_queue.put(
                InstallFinished(
                    component_id="ffmpeg-tools",
                    success=True,
                    message=f"FFmpeg tools installed. ffmpeg={ffmpeg_path} | ffprobe={ffprobe_path}",
                )
            )

        self.show_page("Processing")
        self.task_runner.submit("install-ffmpeg-tools", task)

    def _install_voice_for_language(self, language_code: str) -> None:
        voice_id = default_piper_voice_id(language_code)
        self._install_voice_by_id(voice_id)

    def _install_voice_by_id(self, voice_id: str, *, return_page: str | None = None) -> None:
        self._install_component(f"piper-voice-{voice_id}", f"Piper voice {voice_id}", return_page=return_page)

    def _install_argos_pair(self, source_language: str, target_language: str) -> None:
        def task() -> None:
            component_id = f"argos-{source_language}-{target_language}"
            self.event_queue.put(InstallStarted(component_id=component_id, title="Argos language package"))
            try:
                self.model_manager.install_argos_package(
                    source_language,
                    target_language,
                    lambda message: self.event_queue.put(
                        DownloadProgress(component_id=component_id, progress=0.0, detail=message)
                    ),
                )
            except Exception as exc:
                self.logger.exception("Argos package install failed.")
                self.event_queue.put(InstallFinished(component_id=component_id, success=False, message=str(exc)))
                return
            self.event_queue.put(
                InstallFinished(
                    component_id=component_id,
                    success=True,
                    message=f"Argos package installed for {source_language}->{target_language}.",
                )
            )

        self.show_page("Processing")
        self.task_runner.submit(f"install-argos-{source_language}-{target_language}", task)

    def _install_python_dependencies(self) -> None:
        def task() -> None:
            self.event_queue.put(InstallStarted(component_id="python-deps", title="Python dependencies"))
            try:
                self.python_package_manager.install_requirements(
                    lambda message: self.event_queue.put(
                        DownloadProgress(component_id="python-deps", progress=0.0, detail=message)
                    )
                )
            except Exception as exc:
                self.logger.exception("Python dependency install failed.")
                self.event_queue.put(InstallFinished(component_id="python-deps", success=False, message=str(exc)))
                return
            self.event_queue.put(
                InstallFinished(
                    component_id="python-deps",
                    success=True,
                    message="Python dependencies installed. Restart the app if a loaded module still fails.",
                )
            )

        self.show_page("Processing")
        self.task_runner.submit("install-python-deps", task)

    def select_video_file(self) -> None:
        selected = dialogs.choose_video_file(self)
        if selected is None:
            return
        self.app_state.selected_file = selected
        self.settings_store.update({"last_opened_file": str(selected)})
        self.pages["Home"].update_selected_file(selected)  # type: ignore[call-arg]
        self._update_home_readiness()

    def on_home_settings_changed(self) -> None:
        home_page: HomePage = self.pages["Home"]  # type: ignore[assignment]
        self.app_state.source_language = home_page.get_source_language_code()
        self.app_state.target_language = home_page.get_target_language_code()
        self.app_state.subtitles_enabled = home_page.subtitles_enabled()
        self.app_state.subtitle_language = home_page.get_subtitle_language_code()
        self.app_state.retime_video_to_dub = home_page.retime_video_to_dub_enabled()
        self.app_state.voice_mode = home_page.get_voice_mode()
        self.app_state.speaker_grouping_enabled = self.app_state.voice_mode == "per_speaker"
        self.app_state.max_speaker_voices = home_page.get_max_speaker_voices()
        self.app_state.auto_match_speaker_gender = (
            home_page.auto_match_speaker_gender_enabled() if self.app_state.voice_mode == "per_speaker" else False
        )
        selected_label = home_page.get_preferred_voice_label()
        if self.app_state.voice_mode == "per_speaker":
            self.app_state.preferred_voice_id = ""
            self._update_home_readiness()
            return
        if selected_label == "No installed voice":
            self.app_state.preferred_voice_id = ""
            self._update_home_readiness()
            return
        self.app_state.preferred_voice_id = self._resolve_voice_id_from_label(
            self.app_state.target_language,
            selected_label,
        )
        last_used = dict(self.settings_store.load().last_used_piper_voice_by_language)
        if self.app_state.preferred_voice_id:
            last_used[self.app_state.target_language] = self.app_state.preferred_voice_id
            self.settings_store.update({"last_used_piper_voice_by_language": last_used})
        self._update_home_readiness()

    def on_home_voice_selected(self) -> None:
        home_page: HomePage = self.pages["Home"]  # type: ignore[assignment]
        if home_page.get_voice_mode() == "per_speaker":
            return
        target_language = home_page.get_target_language_code()
        selected_label = home_page.get_preferred_voice_label()
        if selected_label == "No installed voice":
            return
        voice_id = self._resolve_voice_id_from_label(target_language, selected_label)
        if not voice_id or self.model_manager.voice_manager.voice_installed(voice_id):
            return
        if not self._voice_installable(target_language, voice_id):
            dialogs.show_error(
                self,
                "Voice not available",
                f"No managed Piper voice download is available for {selected_label} in {self._language_label(target_language)}.",
            )
            return
        install_now = dialogs.confirm(
            self,
            "Install selected voice",
            f"{selected_label} is not installed yet. Install this Piper voice now so it is ready on the Home page?",
        )
        if install_now:
            self._install_voice_by_id(voice_id, return_page="Home")

    def _resolve_voice_id_from_label(self, language_code: str, label: str) -> str:
        installed = self.model_manager.voice_manager.get_installed_voices(language_code)
        for voice in installed:
            if voice.display_name == label or voice.voice_id == label:
                return voice.voice_id
        for voice in all_voices():
            if voice.display_name == label or voice.voice_id == label:
                return voice.voice_id
        default_preset = DEFAULT_PIPER_VOICE_BY_LANGUAGE.get(language_code)
        return default_preset.voice_id if default_preset else DEFAULT_PIPER_VOICE_BY_LANGUAGE["en"].voice_id

    def get_installed_voices_for_language(self, language_code: str) -> list[str]:
        return [voice.display_name for voice in self.model_manager.voice_manager.get_installed_voices(language_code)]

    def _voice_installable(self, language_code: str, voice_id: str) -> bool:
        return any(voice.voice_id == voice_id for voice in voices_for_language(language_code))

    def _update_home_readiness(self) -> None:
        home_page: HomePage = self.pages["Home"]  # type: ignore[assignment]
        snapshot = self.app_state.environment_snapshot
        multi_voice_note = ""
        if self.app_state.queue_running:
            home_page.update_readiness(
                "Queue is running. Single-video start is paused until the current queue finishes or is cancelled.",
                False,
            )
            return
        if self.app_state.selected_file is None:
            home_page.update_readiness("Select a video file to begin.", False)
            return
        if snapshot is None:
            home_page.update_readiness("Run environment checks on the Setup page before starting.", False)
            return
        if not snapshot.ready:
            home_page.update_readiness("Required runtime components are still missing. Fix them on the Setup page first.", False)
            return
        selected_voice_id = self.app_state.preferred_voice_id or self._resolve_voice_id_from_label(
            self.app_state.target_language,
            home_page.get_preferred_voice_label(),
        )
        available_voice_count = len(self.model_manager.available_voice_ids_for_language(self.app_state.target_language))
        if self.app_state.voice_mode == "single":
            if selected_voice_id and self.model_manager.voice_manager.voice_installed(selected_voice_id):
                pass
            elif selected_voice_id and self._voice_installable(self.app_state.target_language, selected_voice_id):
                home_page.update_readiness("Selected voice is available but not installed yet. Start will offer to install it automatically.", True)
                return
            elif not self.environment_manager.selected_voice_ready(self.app_state.target_language):
                home_page.update_readiness("No managed Piper voice is available for the selected target language yet.", False)
                return
        elif available_voice_count == 0:
            home_page.update_readiness("No managed Piper voices are available for the selected target language yet.", False)
            return
        if self.app_state.voice_mode == "per_speaker":
            speechbrain_item = snapshot.by_key().get("speechbrain_runtime")
            if speechbrain_item and speechbrain_item.status != "ok":
                home_page.update_readiness("Speaker grouping is enabled, but SpeechBrain is not ready.", False)
                return
            if available_voice_count < self.app_state.max_speaker_voices:
                multi_voice_note = (
                    f" Per-speaker mode can auto-install up to {available_voice_count} managed voices for this language and will reuse them if more speakers are detected."
                )
            if self.app_state.auto_match_speaker_gender:
                multi_voice_note += " Gender-aware voice matching will try a best-effort male/female guess from pitch."
        if self.app_state.source_language == "auto":
            if transcript_item := snapshot.by_key().get("argos_runtime"):
                if transcript_item.status != "ok":
                    home_page.update_readiness("Argos Translate runtime is not ready yet.", False)
                    return
            subtitle_note = ""
            if self.app_state.subtitles_enabled:
                subtitle_note = " Subtitle translation packages can also be installed automatically during processing."
            home_page.update_readiness(
                "Environment is ready. If the detected source language needs an Argos package, the app will install it during processing."
                + subtitle_note
                + multi_voice_note,
                True,
            )
            return
        if self.app_state.source_language != "auto" and not self.environment_manager.selected_pair_ready(
            self.app_state.source_language,
            self.app_state.target_language,
        ):
            home_page.update_readiness(
                "Main translation package is not installed yet, but the app can fetch it automatically during processing." + multi_voice_note,
                True,
            )
            return
        if self.app_state.subtitles_enabled:
            home_page.update_readiness(
                "Environment is ready. Missing translation packages for dub or subtitles can be installed automatically while the job runs."
                + multi_voice_note,
                True,
            )
            return
        home_page.update_readiness("Environment is ready. You can start processing." + multi_voice_note, True)

    def start_processing(self) -> None:
        if self.app_state.queue_running:
            dialogs.show_error(self, "Queue running", "Wait for the queue to finish or cancel it before starting a separate single job.")
            return
        if self.job_manager is None or self.app_state.selected_file is None:
            dialogs.show_error(self, "Cannot start", "Select a file and complete setup first.")
            return
        if not self._environment_ready_for_jobs():
            dialogs.show_error(self, "Setup incomplete", "Finish the required Setup items before starting a job.")
            return
        request = self._build_job_request_for_source(self.app_state.selected_file)
        ready, error_message = self._ensure_request_voice_ready(request, interactive=True)
        if error_message and error_message != "Voice installation was cancelled.":
            dialogs.show_error(self, "Voice unavailable", error_message)
            return
        if not ready:
            return
        self._submit_job_request(request)

    def _submit_job_request(self, request: JobRequest, *, show_dialog_on_error: bool = True) -> None:
        if self.job_manager is None:
            if show_dialog_on_error:
                dialogs.show_error(self, "Unable to start job", "The job manager is not available.")
            return
        try:
            self.job_manager.submit(request)
        except Exception as exc:
            active_queue = self._find_queue_item(self.app_state.active_queue_item_id)
            if active_queue is not None and self.app_state.queue_running:
                active_queue.status = "failed"
                active_queue.error_message = str(exc)
                self.app_state.active_queue_item_id = None
                self.pages["Processing"].append_log(f"Queued item failed before start: {exc}")  # type: ignore[call-arg]
                self.after(150, self._start_next_queued_job)
                self._refresh_visible_pages()
                return
            if show_dialog_on_error:
                dialogs.show_error(self, "Unable to start job", str(exc))

    def cancel_current_job(self) -> None:
        if self.app_state.queue_running:
            self.app_state.queue_running = False
            self.pages["Processing"].append_log("Queue stop requested. The current job will cancel and remaining queued items will stay pending.")  # type: ignore[call-arg]
            self._refresh_visible_pages()
        if self.job_manager is not None:
            self.job_manager.cancel()

    def export_transcript_json(self) -> None:
        result = self.app_state.latest_result
        if result:
            open_in_explorer(result.output_paths.transcript_json)

    def export_words_json(self) -> None:
        result = self.app_state.latest_result
        if result:
            open_in_explorer(result.output_paths.words_json)

    def export_srt(self) -> None:
        result = self.app_state.latest_result
        if result and result.output_paths.subtitles_srt:
            open_in_explorer(result.output_paths.subtitles_srt)

    def open_project_folder(self) -> None:
        result = self.app_state.latest_result
        if result:
            open_in_explorer(result.output_paths.project_folder)

    def copy_output_path(self, output_key: str) -> None:
        result = self.app_state.latest_result
        if result is None:
            return
        path_map = {
            "dubbed_video": result.output_paths.dubbed_video,
            "transcript_json": result.output_paths.transcript_json,
            "words_json": result.output_paths.words_json,
            "translated_segments_json": result.output_paths.translated_segments_json,
            "subtitles_srt": result.output_paths.subtitles_srt,
        }
        selected = path_map.get(output_key)
        if selected is None:
            return
        self.clipboard_clear()
        self.clipboard_append(str(selected))

    def save_default_languages(self, source_language: str, target_language: str) -> None:
        settings = self.settings_store.update(
            {
                "default_source_language": source_language,
                "default_target_language": target_language,
            }
        )
        self.app_state.settings = settings
        self._load_settings_into_pages()
        self.on_home_settings_changed()

    def save_default_processing(
        self,
        *,
        voice_mode: str,
        max_speaker_voices: int,
        auto_match_speaker_gender: bool,
        subtitles_enabled: bool,
        subtitle_language: str,
        retime_video_to_dub: bool,
    ) -> None:
        settings = self.settings_store.update(
            {
                "default_voice_mode": voice_mode,
                "speaker_grouping_enabled": voice_mode == "per_speaker",
                "default_max_speaker_voices": max_speaker_voices,
                "auto_match_speaker_gender": auto_match_speaker_gender if voice_mode == "per_speaker" else False,
                "subtitles_enabled": subtitles_enabled,
                "default_subtitle_language": subtitle_language,
                "retime_video_to_dub": retime_video_to_dub,
                "appearance_mode": "dark",
            }
        )
        self.app_state.settings = settings
        self._load_settings_into_pages()
        self.on_home_settings_changed()

    def clear_cache(self) -> None:
        if dialogs.confirm(self, "Clear cache", "Delete files from the managed cache folder?"):
            self.environment_manager.clear_cache()
            self.run_environment_scan()

    def remove_all_app_data(self) -> None:
        processing_page: ProcessingPage = self.pages["Processing"]  # type: ignore[assignment]
        if processing_page.status_label.cget("text") == "Running":
            dialogs.show_error(self, "Cannot reset now", "Wait for the current job to finish or cancel it before removing all app data.")
            return
        first_confirm = dialogs.confirm(
            self,
            "Remove all app data",
            "This will delete all managed models, voices, caches, logs, settings, project files, and exports under data/. The app will restart into a clean first-run state.",
        )
        if not first_confirm:
            return
        final_confirm = dialogs.confirm(
            self,
            "Final confirmation",
            "This action cannot be undone. Continue and wipe all AutoDub Studio data now?",
        )
        if not final_confirm:
            return
        try:
            shutdown_logging_handlers()
            self.environment_manager.remove_all_managed_data()
            relaunch_startup(self.paths.root / "start.pyw", self.paths.root)
        except Exception as exc:
            dialogs.show_error(self, "Reset failed", str(exc))
            return
        self.destroy()

    def open_logs_folder(self) -> None:
        open_in_explorer(self.paths.logs)

    def open_models_folder(self) -> None:
        open_in_explorer(self.paths.models)
