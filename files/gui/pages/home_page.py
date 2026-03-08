"""Home page for job setup."""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from files.constants import DEFAULT_MAX_SPEAKER_VOICES
from files.constants import LANGUAGE_LABELS, SUBTITLE_LANGUAGE_LABELS, SUPPORTED_DUB_LANGUAGE_CODES
from files.core.result_types import QueuedJob
from files.gui.theme import TEXT_MUTED, WARNING_COLOR, ui_font
from files.gui.widgets.dropzone import Dropzone
from files.gui.widgets.labeled_value import LabeledValue
from files.gui.widgets.section_card import SectionCard
from files.tts.voice_registry import voices_for_language
from files.utils.file_utils import file_size_mb


VOICE_MODE_LABELS = {
    "single": "Single voice",
    "per_speaker": "One voice per detected speaker",
}


def _subtitle_language_values() -> list[str]:
    return list(SUBTITLE_LANGUAGE_LABELS.values()) + [LANGUAGE_LABELS[key] for key in LANGUAGE_LABELS if key != "auto"]


def _target_language_values() -> list[str]:
    return [LANGUAGE_LABELS[key] for key in SUPPORTED_DUB_LANGUAGE_CODES]


MAX_SPEAKER_VOICE_VALUES = [str(value) for value in range(1, 7)]


class HomePage(ctk.CTkScrollableFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self._refreshing = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        brand_card = SectionCard(
            self,
            "AutoDub Studio",
            "Load a local video, choose the target language, and run the fixed offline dubbing pipeline.",
        )
        brand_card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(24, 16))
        self.dropzone = Dropzone(self, self.controller.select_video_file)
        self.dropzone.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=(0, 16))
        self.file_card = SectionCard(self, "Selected File", "The input video stays untouched. Processing happens in a managed project folder.")
        self.file_card.grid(row=1, column=1, sticky="nsew", padx=(12, 24), pady=(0, 16))
        self.file_name = LabeledValue(self.file_card, "Name", "No file selected")
        self.file_name.grid(row=2, column=0, sticky="ew", padx=18, pady=4)
        self.file_path = LabeledValue(self.file_card, "Path", "")
        self.file_path.grid(row=3, column=0, sticky="ew", padx=18, pady=4)
        self.file_size = LabeledValue(self.file_card, "Size", "")
        self.file_size.grid(row=4, column=0, sticky="ew", padx=18, pady=(4, 18))
        self.config_card = SectionCard(self, "Dub Settings", "Choose languages and voice behavior. Backend selection is intentionally hidden because the stack is fixed.")
        self.config_card.grid(row=2, column=0, sticky="nsew", padx=(24, 12), pady=(0, 24))
        self.config_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.config_card, text="Source language", text_color=TEXT_MUTED, font=ui_font(12)).grid(row=2, column=0, sticky="w", padx=18, pady=6)
        self.source_menu = ctk.CTkOptionMenu(
            self.config_card,
            values=[LANGUAGE_LABELS[key] for key in LANGUAGE_LABELS],
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _: self._handle_home_setting_change(),
        )
        self.source_menu.grid(row=2, column=1, sticky="ew", padx=18, pady=6)
        ctk.CTkLabel(self.config_card, text="Target language", text_color=TEXT_MUTED, font=ui_font(12)).grid(row=3, column=0, sticky="w", padx=18, pady=6)
        self.target_menu = ctk.CTkOptionMenu(
            self.config_card,
            values=_target_language_values(),
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _: self._target_language_changed(),
        )
        self.target_menu.grid(row=3, column=1, sticky="ew", padx=18, pady=6)
        ctk.CTkLabel(self.config_card, text="Voice mode", text_color=TEXT_MUTED, font=ui_font(12)).grid(row=4, column=0, sticky="w", padx=18, pady=6)
        self.voice_mode_menu = ctk.CTkOptionMenu(
            self.config_card,
            values=list(VOICE_MODE_LABELS.values()),
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _: self._voice_mode_changed(),
        )
        self.voice_mode_menu.grid(row=4, column=1, sticky="ew", padx=18, pady=6)
        ctk.CTkLabel(self.config_card, text="Max speaker voices", text_color=TEXT_MUTED, font=ui_font(12)).grid(row=5, column=0, sticky="w", padx=18, pady=6)
        self.max_voices_menu = ctk.CTkOptionMenu(
            self.config_card,
            values=MAX_SPEAKER_VOICE_VALUES,
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _: self._handle_home_setting_change(),
        )
        self.max_voices_menu.grid(row=5, column=1, sticky="ew", padx=18, pady=6)
        self.overflow_label = ctk.CTkLabel(
            self.config_card,
            text="If more speakers are detected than this limit, downloaded voices are reused at random.",
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=540,
            font=ui_font(11),
        )
        self.overflow_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.gender_match_switch = ctk.CTkSwitch(
            self.config_card,
            text="Try gender-aware voice matching",
            font=ui_font(12),
            command=lambda: self._handle_home_setting_change(),
        )
        self.gender_match_switch.grid(row=7, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 6))
        self.gender_match_help = ctk.CTkLabel(
            self.config_card,
            text="Uses the local audEERING age/gender model and then prefers matching Piper voices when the result is confident.",
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=540,
            font=ui_font(11),
        )
        self.gender_match_help.grid(row=8, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.experimental_warning = ctk.CTkLabel(
            self.config_card,
            text=(
                "Experimental: multi-speaker mode is still best-effort and can mis-detect or merge speakers. "
                "If you do not need separate voices, use Single voice for the most stable results."
            ),
            text_color=WARNING_COLOR,
            justify="left",
            wraplength=540,
            font=ui_font(11, weight="bold"),
        )
        self.experimental_warning.grid(row=9, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.subtitle_switch = ctk.CTkSwitch(
            self.config_card,
            text="Create subtitles and burn them into the exported video",
            font=ui_font(12),
            command=self._subtitle_toggle_changed,
        )
        self.subtitle_switch.grid(row=10, column=0, columnspan=2, sticky="w", padx=18, pady=8)
        ctk.CTkLabel(self.config_card, text="Subtitle language", text_color=TEXT_MUTED, font=ui_font(12)).grid(row=11, column=0, sticky="w", padx=18, pady=6)
        self.subtitle_menu = ctk.CTkOptionMenu(
            self.config_card,
            values=_subtitle_language_values(),
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _: self._handle_home_setting_change(),
        )
        self.subtitle_menu.grid(row=11, column=1, sticky="ew", padx=18, pady=6)
        self.retime_switch = ctk.CTkSwitch(
            self.config_card,
            text="Match video timing to natural dub speech",
            font=ui_font(12),
            command=self.controller.on_home_settings_changed,
        )
        self.retime_switch.grid(row=12, column=0, columnspan=2, sticky="w", padx=18, pady=8)
        self.retime_help = ctk.CTkLabel(
            self.config_card,
            text=(
                "On: the video is sped up or slowed down so the natural dub fits. "
                "Off: the video keeps its original timing and the dub is placed on the original timeline."
            ),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=540,
            font=ui_font(11),
        )
        self.retime_help.grid(row=13, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.voice_label = ctk.CTkLabel(self.config_card, text="Preferred voice", text_color=TEXT_MUTED, font=ui_font(12))
        self.voice_label.grid(row=14, column=0, sticky="w", padx=18, pady=6)
        self.voice_menu = ctk.CTkOptionMenu(
            self.config_card,
            values=["No installed voice"],
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _: self._voice_selection_changed(),
        )
        self.voice_menu.grid(row=14, column=1, sticky="ew", padx=18, pady=6)
        self.voice_help = ctk.CTkLabel(
            self.config_card,
            text="Single-voice mode uses the selected voice. Per-speaker mode chooses and tops up a voice pool automatically.",
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=540,
            font=ui_font(11),
        )
        self.voice_help.grid(row=15, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.start_button = ctk.CTkButton(self.config_card, text="Start Processing", height=38, font=ui_font(12), command=self.controller.start_processing)
        self.start_button.grid(row=16, column=0, columnspan=2, sticky="ew", padx=18, pady=(12, 18))
        self.readiness_card = SectionCard(self, "Readiness Summary", "")
        self.readiness_card.grid(row=2, column=1, sticky="nsew", padx=(12, 24), pady=(0, 24))
        self.readiness_label = ctk.CTkLabel(
            self.readiness_card,
            text="Run setup checks to see whether the environment is ready.",
            justify="left",
            wraplength=420,
            font=ui_font(12),
        )
        self.readiness_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        ctk.CTkButton(self.readiness_card, text="Open Setup", font=ui_font(12), command=lambda: self.controller.show_page("Setup")).grid(
            row=3, column=0, sticky="w", padx=18, pady=(0, 18)
        )
        self.queue_card = SectionCard(
            self,
            "Queue",
            "Batch several videos with the current settings. Each queued item keeps the settings it had when you added it, and jobs run one after another.",
        )
        self.queue_card.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=24, pady=(0, 24))
        controls = ctk.CTkFrame(self.queue_card, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        controls.grid_columnconfigure(3, weight=1)
        self.add_videos_button = ctk.CTkButton(
            controls,
            text="Add videos",
            font=ui_font(12),
            command=self.controller.add_videos_to_queue,
        )
        self.add_videos_button.grid(row=0, column=0, padx=(0, 10))
        self.start_queue_button = ctk.CTkButton(
            controls,
            text="Start queue",
            font=ui_font(12),
            command=self.controller.start_queue,
        )
        self.start_queue_button.grid(row=0, column=1, padx=(0, 10))
        self.clear_queue_button = ctk.CTkButton(
            controls,
            text="Clear queue",
            font=ui_font(12),
            fg_color="#223244",
            hover_color="#314359",
            command=self.controller.clear_queue,
        )
        self.clear_queue_button.grid(row=0, column=2)
        self.queue_summary_label = ctk.CTkLabel(
            self.queue_card,
            text="Queue is empty.",
            justify="left",
            wraplength=980,
            text_color=TEXT_MUTED,
            font=ui_font(11),
        )
        self.queue_summary_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 10))
        self.queue_list = ctk.CTkScrollableFrame(self.queue_card, fg_color="transparent", height=240)
        self.queue_list.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.queue_list.grid_columnconfigure(0, weight=1)
        self.queue_empty_label = ctk.CTkLabel(
            self.queue_list,
            text="No queued videos yet. Add one or more videos to build a serial batch.",
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=960,
            font=ui_font(12),
        )
        self.queue_empty_label.grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self._refreshing = True
        try:
            self.source_menu.set(LANGUAGE_LABELS["auto"])
            self.target_menu.set(LANGUAGE_LABELS["en"])
            self.voice_mode_menu.set(VOICE_MODE_LABELS["single"])
            self.max_voices_menu.set(str(DEFAULT_MAX_SPEAKER_VOICES))
            self.subtitle_menu.set(SUBTITLE_LANGUAGE_LABELS["target"])
            self.gender_match_switch.deselect()
        finally:
            self._refreshing = False
        self.retime_switch.select()
        self.subtitle_switch.select()
        self._update_subtitle_menu_state()
        self._update_voice_mode_state()

    def _target_language_changed(self) -> None:
        if self._refreshing:
            return
        self._refresh_voice_options()
        self.controller.on_home_settings_changed()

    def _handle_home_setting_change(self) -> None:
        if self._refreshing:
            return
        self.controller.on_home_settings_changed()

    def _voice_selection_changed(self) -> None:
        if self._refreshing:
            return
        self.controller.on_home_voice_selected()
        self.controller.on_home_settings_changed()

    def _voice_mode_changed(self) -> None:
        if self._refreshing:
            return
        self._update_voice_mode_state()
        self.controller.on_home_settings_changed()

    def _subtitle_toggle_changed(self) -> None:
        if self._refreshing:
            return
        self._update_subtitle_menu_state()
        self.controller.on_home_settings_changed()

    def _update_subtitle_menu_state(self) -> None:
        self.subtitle_menu.configure(state="normal" if self.subtitles_enabled() else "disabled")

    def _update_voice_mode_state(self) -> None:
        per_speaker = self.get_voice_mode() == "per_speaker"
        self.max_voices_menu.configure(state="normal" if per_speaker else "disabled")
        self.gender_match_switch.configure(state="normal" if per_speaker else "disabled")
        self.voice_menu.configure(state="disabled" if per_speaker else "normal")
        self.voice_label.configure(text_color=TEXT_MUTED if not per_speaker else "#63758a")
        self.voice_help.configure(
            text=(
                "Per-speaker mode automatically turns speaker grouping on, ignores the preferred voice, and tops up voices when possible."
                if per_speaker
                else "Single-voice mode uses the selected voice. Per-speaker mode chooses and tops up a voice pool automatically."
            )
        )
        if per_speaker:
            self.experimental_warning.grid()
            self.gender_match_help.configure(text_color=TEXT_MUTED)
        else:
            self.experimental_warning.grid_remove()
            self.gender_match_help.configure(text_color="#63758a")

    def _refresh_voice_options(self) -> None:
        target_code = self.get_target_language_code()
        installed = self.controller.get_installed_voices_for_language(target_code)
        values = installed or [voice.display_name for voice in voices_for_language(target_code)] or ["No installed voice"]
        self.voice_menu.configure(values=values)
        current = self.voice_menu.get()
        selected = current if current in values else values[0]
        self._refreshing = True
        try:
            self.voice_menu.set(selected)
        finally:
            self._refreshing = False

    def apply_settings(
        self,
        *,
        source_language_label: str,
        target_language_label: str,
        voice_mode_label: str,
        max_speaker_voices: int,
        auto_match_speaker_gender: bool,
        subtitles_enabled: bool,
        subtitle_language_label: str,
        retime_video_to_dub: bool,
    ) -> None:
        self._refreshing = True
        try:
            self.source_menu.set(source_language_label)
            self.target_menu.set(target_language_label)
            self.voice_mode_menu.set(voice_mode_label)
            self.max_voices_menu.set(str(max_speaker_voices))
            if auto_match_speaker_gender:
                self.gender_match_switch.select()
            else:
                self.gender_match_switch.deselect()
            if subtitles_enabled:
                self.subtitle_switch.select()
            else:
                self.subtitle_switch.deselect()
            self.subtitle_menu.set(subtitle_language_label)
            if retime_video_to_dub:
                self.retime_switch.select()
            else:
                self.retime_switch.deselect()
            self._refresh_voice_options()
        finally:
            self._refreshing = False
        self._update_subtitle_menu_state()
        self._update_voice_mode_state()

    def update_selected_file(self, path: Path | None) -> None:
        if path is None:
            self.file_name.set_value("No file selected")
            self.file_path.set_value("")
            self.file_size.set_value("")
            return
        self.file_name.set_value(path.name)
        self.file_path.set_value(str(path))
        self.file_size.set_value(f"{file_size_mb(path):.2f} MB")

    def update_readiness(self, message: str, enabled: bool) -> None:
        self.readiness_label.configure(text=message)
        self.start_button.configure(state="normal" if enabled else "disabled")

    def update_queue(self, queue_items: list[QueuedJob], queue_running: bool) -> None:
        for child in self.queue_list.winfo_children():
            child.destroy()
        if not queue_items:
            self.queue_empty_label = ctk.CTkLabel(
                self.queue_list,
                text="No queued videos yet. Add one or more videos to build a serial batch.",
                text_color=TEXT_MUTED,
                justify="left",
                wraplength=960,
                font=ui_font(12),
            )
            self.queue_empty_label.grid(row=0, column=0, sticky="w", padx=6, pady=6)
        else:
            for index, item in enumerate(queue_items):
                row = ctk.CTkFrame(self.queue_list, corner_radius=12, fg_color="#182230", border_width=1, border_color="#263244")
                row.grid(row=index, column=0, sticky="ew", pady=(0, 8))
                row.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(row, text=f"{index + 1}. {item.source_name}", font=ui_font(13, weight="bold")).grid(
                    row=0, column=0, sticky="w", padx=12, pady=(10, 2)
                )
                status_text, status_color = self._queue_status_chip(item.status)
                ctk.CTkLabel(
                    row,
                    text=status_text,
                    fg_color=status_color,
                    corner_radius=999,
                    text_color="white",
                    font=ui_font(10, weight="bold"),
                    padx=10,
                    pady=2,
                ).grid(row=0, column=1, sticky="e", padx=12, pady=(10, 2))
                ctk.CTkLabel(
                    row,
                    text=self._queue_request_summary(item),
                    text_color=TEXT_MUTED,
                    justify="left",
                    wraplength=820,
                    font=ui_font(11),
                ).grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))
                if item.error_message:
                    ctk.CTkLabel(
                        row,
                        text=item.error_message,
                        text_color=WARNING_COLOR,
                        justify="left",
                        wraplength=820,
                        font=ui_font(10),
                    ).grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))
                    button_row = 3
                else:
                    button_row = 2
                remove_button = ctk.CTkButton(
                    row,
                    text="Remove",
                    width=90,
                    height=28,
                    font=ui_font(11),
                    state="disabled" if queue_running else "normal",
                    command=lambda queue_id=item.queue_id: self.controller.remove_queue_item(queue_id),
                )
                remove_button.grid(row=button_row, column=0, sticky="w", padx=12, pady=(0, 10))

        pending_count = sum(1 for item in queue_items if item.status == "pending")
        running_count = sum(1 for item in queue_items if item.status == "running")
        completed_count = sum(1 for item in queue_items if item.status == "completed")
        failed_count = sum(1 for item in queue_items if item.status == "failed")
        if queue_running:
            summary = (
                f"Queue running: {running_count or 1} active, {pending_count} pending, "
                f"{completed_count} completed, {failed_count} failed."
            )
        else:
            summary = (
                f"{len(queue_items)} item(s) in queue. "
                f"{pending_count} pending, {completed_count} completed, {failed_count} failed."
                if queue_items
                else "Queue is empty."
            )
        self.queue_summary_label.configure(text=summary)
        add_state = "disabled" if queue_running else "normal"
        self.add_videos_button.configure(state=add_state)
        self.clear_queue_button.configure(state="disabled" if queue_running or not queue_items else "normal")
        self.start_queue_button.configure(
            state="disabled" if queue_running or pending_count == 0 else "normal",
            text="Queue running..." if queue_running else "Start queue",
        )

    def _queue_status_chip(self, status: str) -> tuple[str, str]:
        mapping = {
            "pending": ("QUEUED", "#1c7ed6"),
            "running": ("RUNNING", "#f08c00"),
            "completed": ("DONE", "#2f9e44"),
            "failed": ("FAILED", WARNING_COLOR),
        }
        return mapping.get(status, ("QUEUED", "#1c7ed6"))

    def _queue_request_summary(self, item: QueuedJob) -> str:
        request = item.request
        source_label = LANGUAGE_LABELS.get(request.source_language, request.source_language)
        target_label = LANGUAGE_LABELS.get(request.target_language, request.target_language)
        voice_text = "Single voice" if request.voice_mode == "single" else f"Per-speaker voices (max {request.max_speaker_voices})"
        if request.voice_mode == "per_speaker" and request.auto_match_speaker_gender:
            voice_text += ", gender-aware"
        subtitle_text = "Subtitles on" if request.subtitles_enabled else "Subtitles off"
        timing_text = "Retune video timing" if request.retime_video_to_dub else "Keep original video timing"
        return f"{source_label} -> {target_label} | {voice_text} | {subtitle_text} | {timing_text}"

    def get_source_language_code(self) -> str:
        label = self.source_menu.get()
        return next(code for code, text in LANGUAGE_LABELS.items() if text == label)

    def get_target_language_code(self) -> str:
        label = self.target_menu.get()
        return next(code for code, text in LANGUAGE_LABELS.items() if text == label)

    def get_voice_mode(self) -> str:
        label = self.voice_mode_menu.get()
        return next(code for code, text in VOICE_MODE_LABELS.items() if text == label)

    def get_preferred_voice_label(self) -> str:
        return self.voice_menu.get()

    def speaker_grouping_enabled(self) -> bool:
        return self.get_voice_mode() == "per_speaker"

    def subtitles_enabled(self) -> bool:
        return self.subtitle_switch.get() == 1

    def get_subtitle_language_code(self) -> str:
        label = self.subtitle_menu.get()
        if label in SUBTITLE_LANGUAGE_LABELS.values():
            return next(code for code, text in SUBTITLE_LANGUAGE_LABELS.items() if text == label)
        return next(code for code, text in LANGUAGE_LABELS.items() if text == label)

    def retime_video_to_dub_enabled(self) -> bool:
        return self.retime_switch.get() == 1

    def get_max_speaker_voices(self) -> int:
        try:
            return max(1, int(self.max_voices_menu.get()))
        except ValueError:
            return DEFAULT_MAX_SPEAKER_VOICES

    def auto_match_speaker_gender_enabled(self) -> bool:
        return self.gender_match_switch.get() == 1
