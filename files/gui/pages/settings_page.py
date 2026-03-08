"""Settings and diagnostics page."""

from __future__ import annotations

import json

import customtkinter as ctk

from files.constants import DEFAULT_MAX_SPEAKER_VOICES
from files.constants import LANGUAGE_LABELS, SUBTITLE_LANGUAGE_LABELS, SUPPORTED_DUB_LANGUAGE_CODES
from files.gui.theme import ERROR_COLOR, TEXT_MUTED, WARNING_COLOR, ui_font
from files.gui.widgets.labeled_value import LabeledValue
from files.gui.widgets.section_card import SectionCard


VOICE_MODE_LABELS = {
    "single": "Single voice",
    "per_speaker": "One voice per detected speaker",
}


def _subtitle_language_values() -> list[str]:
    return list(SUBTITLE_LANGUAGE_LABELS.values()) + [LANGUAGE_LABELS[key] for key in LANGUAGE_LABELS if key != "auto"]


def _subtitle_code_from_label(label: str) -> str:
    if label in SUBTITLE_LANGUAGE_LABELS.values():
        return next(code for code, text in SUBTITLE_LANGUAGE_LABELS.items() if text == label)
    return next(code for code, text in LANGUAGE_LABELS.items() if text == label)


def _subtitle_label_for_code(code: str) -> str:
    if code in SUBTITLE_LANGUAGE_LABELS:
        return SUBTITLE_LANGUAGE_LABELS[code]
    return LANGUAGE_LABELS.get(code, LANGUAGE_LABELS["en"])


def _target_language_values() -> list[str]:
    return [LANGUAGE_LABELS[key] for key in SUPPORTED_DUB_LANGUAGE_CODES]


MAX_SPEAKER_VOICE_VALUES = [str(value) for value in range(1, 7)]


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self._refreshing = False
        self.grid_columnconfigure(0, weight=1)

        self.summary_card = SectionCard(
            self,
            "Settings",
            "Review managed paths, default processing values, and installed local components. The app now stays in a fixed dark appearance mode.",
        )
        self.summary_card.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 16))
        self.mode_value = LabeledValue(self.summary_card, "Appearance mode", "Dark only")
        self.mode_value.grid(row=2, column=0, sticky="ew", padx=18, pady=4)
        self.settings_path_value = LabeledValue(self.summary_card, "Settings file")
        self.settings_path_value.grid(row=3, column=0, sticky="ew", padx=18, pady=4)

        self.paths_card = SectionCard(self, "Paths", "Review the managed directories and detected FFmpeg tools.")
        self.paths_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        self.path_rows = {
            "ffmpeg": LabeledValue(self.paths_card, "FFmpeg"),
            "ffprobe": LabeledValue(self.paths_card, "ffprobe"),
            "logs": LabeledValue(self.paths_card, "Logs"),
            "models": LabeledValue(self.paths_card, "Models"),
            "projects": LabeledValue(self.paths_card, "Projects"),
            "exports": LabeledValue(self.paths_card, "Exports"),
        }
        for index, widget in enumerate(self.path_rows.values(), start=2):
            widget.grid(row=index, column=0, sticky="ew", padx=18, pady=4)
        actions = ctk.CTkFrame(self.paths_card, fg_color="transparent")
        actions.grid(row=8, column=0, sticky="w", padx=18, pady=(12, 18))
        ctk.CTkButton(actions, text="Open logs folder", font=ui_font(12), command=self.controller.open_logs_folder).grid(
            row=0, column=0, padx=(0, 10)
        )
        ctk.CTkButton(actions, text="Open models folder", font=ui_font(12), command=self.controller.open_models_folder).grid(
            row=0, column=1, padx=(0, 10)
        )
        ctk.CTkButton(actions, text="Clear cache", font=ui_font(12), command=self.controller.clear_cache).grid(row=0, column=2)
        ctk.CTkButton(
            actions,
            text="Remove all app data",
            font=ui_font(12),
            fg_color=ERROR_COLOR,
            hover_color="#c92a2a",
            command=self.controller.remove_all_app_data,
        ).grid(row=0, column=3, padx=(10, 0))

        self.defaults_card = SectionCard(self, "Defaults", "Changing these values updates the saved defaults and the Home page immediately.")
        self.defaults_card.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        self.defaults_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.defaults_card, text="Default source language", text_color=TEXT_MUTED, font=ui_font(12)).grid(
            row=2, column=0, sticky="w", padx=18, pady=6
        )
        self.source_menu = ctk.CTkOptionMenu(
            self.defaults_card,
            values=[LANGUAGE_LABELS[key] for key in LANGUAGE_LABELS],
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _value: self._handle_language_change(),
        )
        self.source_menu.grid(row=2, column=1, sticky="ew", padx=18, pady=6)
        ctk.CTkLabel(self.defaults_card, text="Default target language", text_color=TEXT_MUTED, font=ui_font(12)).grid(
            row=3, column=0, sticky="w", padx=18, pady=6
        )
        self.target_menu = ctk.CTkOptionMenu(
            self.defaults_card,
            values=_target_language_values(),
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _value: self._handle_language_change(),
        )
        self.target_menu.grid(row=3, column=1, sticky="ew", padx=18, pady=6)
        ctk.CTkLabel(self.defaults_card, text="Default voice mode", text_color=TEXT_MUTED, font=ui_font(12)).grid(
            row=4, column=0, sticky="w", padx=18, pady=6
        )
        self.voice_mode_menu = ctk.CTkOptionMenu(
            self.defaults_card,
            values=list(VOICE_MODE_LABELS.values()),
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _value: self._handle_voice_mode_change(),
        )
        self.voice_mode_menu.grid(row=4, column=1, sticky="ew", padx=18, pady=6)
        ctk.CTkLabel(self.defaults_card, text="Default max speaker voices", text_color=TEXT_MUTED, font=ui_font(12)).grid(
            row=5, column=0, sticky="w", padx=18, pady=6
        )
        self.max_voices_menu = ctk.CTkOptionMenu(
            self.defaults_card,
            values=MAX_SPEAKER_VOICE_VALUES,
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _value: self._handle_max_voices_change(),
        )
        self.max_voices_menu.grid(row=5, column=1, sticky="ew", padx=18, pady=6)
        self.overflow_label = ctk.CTkLabel(
            self.defaults_card,
            text="If more speakers are detected than this limit, installed voices are reused at random.",
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=620,
            font=ui_font(11),
        )
        self.overflow_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.gender_match_switch = ctk.CTkSwitch(
            self.defaults_card,
            text="Try gender-aware voice matching by default",
            font=ui_font(12),
            command=self._handle_gender_match_change,
        )
        self.gender_match_switch.grid(row=7, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 6))
        self.gender_match_help = ctk.CTkLabel(
            self.defaults_card,
            text="Per-speaker jobs use the local audEERING age/gender model and then prefer matching local voices when the result is confident.",
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=620,
            font=ui_font(11),
        )
        self.gender_match_help.grid(row=8, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.experimental_warning = ctk.CTkLabel(
            self.defaults_card,
            text=(
                "Experimental: one voice per detected speaker is still best-effort and can mis-detect, merge, or over-split speakers. "
                "Use Single voice unless you specifically need separate speaker voices."
            ),
            text_color=WARNING_COLOR,
            justify="left",
            wraplength=620,
            font=ui_font(11, weight="bold"),
        )
        self.experimental_warning.grid(row=9, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        self.subtitle_switch = ctk.CTkSwitch(
            self.defaults_card,
            text="Create subtitles and burn them into the exported video by default",
            font=ui_font(12),
            command=self._handle_subtitle_toggle_change,
        )
        self.subtitle_switch.grid(row=10, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))
        ctk.CTkLabel(self.defaults_card, text="Default subtitle language", text_color=TEXT_MUTED, font=ui_font(12)).grid(
            row=11, column=0, sticky="w", padx=18, pady=6
        )
        self.subtitle_menu = ctk.CTkOptionMenu(
            self.defaults_card,
            values=_subtitle_language_values(),
            font=ui_font(12),
            dropdown_font=ui_font(12),
            command=lambda _value: self._handle_subtitle_language_change(),
        )
        self.subtitle_menu.grid(row=11, column=1, sticky="ew", padx=18, pady=6)
        self.retime_switch = ctk.CTkSwitch(
            self.defaults_card,
            text="Match video timing to natural dub by default",
            font=ui_font(12),
            command=self._handle_retime_change,
        )
        self.retime_switch.grid(row=12, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 12))
        self.retime_help = ctk.CTkLabel(
            self.defaults_card,
            text=(
                "On: new jobs speed up or slow down the video to follow the natural dub length. "
                "Off: new jobs keep the original video timing and place the dub on the original timeline."
            ),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=620,
            font=ui_font(11),
        )
        self.retime_help.grid(row=13, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 10))
        self.defaults_status = ctk.CTkLabel(
            self.defaults_card,
            text="Saved defaults will be used for new sessions.",
            text_color=TEXT_MUTED,
            font=ui_font(12),
        )
        self.defaults_status.grid(row=14, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 18))

        self.install_card = SectionCard(self, "Installed Components", "Current fixed-stack assets known to the application.")
        self.install_card.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 24))
        self.install_text = ctk.CTkTextbox(self.install_card, height=220, font=ui_font(11))
        self.install_text.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))

    def _code_from_label(self, label: str) -> str:
        return next(code for code, text in LANGUAGE_LABELS.items() if text == label)

    def _voice_mode_from_label(self, label: str) -> str:
        return next(code for code, text in VOICE_MODE_LABELS.items() if text == label)

    def _handle_language_change(self) -> None:
        if self._refreshing:
            return
        self.controller.save_default_languages(
            self._code_from_label(self.source_menu.get()),
            self._code_from_label(self.target_menu.get()),
        )
        self.defaults_status.configure(text="Default languages updated.")

    def _handle_voice_mode_change(self) -> None:
        if self._refreshing:
            return
        self._update_voice_mode_state()
        self.controller.save_default_processing(
            voice_mode=self._voice_mode_from_label(self.voice_mode_menu.get()),
            max_speaker_voices=self._max_speaker_voices(),
            auto_match_speaker_gender=self.gender_match_switch.get() == 1,
            subtitles_enabled=self.subtitle_switch.get() == 1,
            subtitle_language=self._subtitle_code_from_label(self.subtitle_menu.get()),
            retime_video_to_dub=self.retime_switch.get() == 1,
        )
        self.defaults_status.configure(text="Default voice mode updated.")

    def _handle_max_voices_change(self) -> None:
        if self._refreshing:
            return
        self.controller.save_default_processing(
            voice_mode=self._voice_mode_from_label(self.voice_mode_menu.get()),
            max_speaker_voices=self._max_speaker_voices(),
            auto_match_speaker_gender=self.gender_match_switch.get() == 1,
            subtitles_enabled=self.subtitle_switch.get() == 1,
            subtitle_language=self._subtitle_code_from_label(self.subtitle_menu.get()),
            retime_video_to_dub=self.retime_switch.get() == 1,
        )
        self.defaults_status.configure(text="Default max speaker voices updated.")

    def _handle_gender_match_change(self) -> None:
        if self._refreshing:
            return
        self.controller.save_default_processing(
            voice_mode=self._voice_mode_from_label(self.voice_mode_menu.get()),
            max_speaker_voices=self._max_speaker_voices(),
            auto_match_speaker_gender=self.gender_match_switch.get() == 1,
            subtitles_enabled=self.subtitle_switch.get() == 1,
            subtitle_language=self._subtitle_code_from_label(self.subtitle_menu.get()),
            retime_video_to_dub=self.retime_switch.get() == 1,
        )
        self.defaults_status.configure(text="Default gender-aware matching updated.")

    def _handle_subtitle_toggle_change(self) -> None:
        if self._refreshing:
            return
        self.subtitle_menu.configure(state="normal" if self.subtitle_switch.get() == 1 else "disabled")
        self.controller.save_default_processing(
            voice_mode=self._voice_mode_from_label(self.voice_mode_menu.get()),
            max_speaker_voices=self._max_speaker_voices(),
            auto_match_speaker_gender=self.gender_match_switch.get() == 1,
            subtitles_enabled=self.subtitle_switch.get() == 1,
            subtitle_language=self._subtitle_code_from_label(self.subtitle_menu.get()),
            retime_video_to_dub=self.retime_switch.get() == 1,
        )
        self.defaults_status.configure(text="Default subtitle setting updated.")

    def _handle_subtitle_language_change(self) -> None:
        if self._refreshing:
            return
        self.controller.save_default_processing(
            voice_mode=self._voice_mode_from_label(self.voice_mode_menu.get()),
            max_speaker_voices=self._max_speaker_voices(),
            auto_match_speaker_gender=self.gender_match_switch.get() == 1,
            subtitles_enabled=self.subtitle_switch.get() == 1,
            subtitle_language=self._subtitle_code_from_label(self.subtitle_menu.get()),
            retime_video_to_dub=self.retime_switch.get() == 1,
        )
        self.defaults_status.configure(text="Default subtitle language updated.")

    def _handle_retime_change(self) -> None:
        if self._refreshing:
            return
        self.controller.save_default_processing(
            voice_mode=self._voice_mode_from_label(self.voice_mode_menu.get()),
            max_speaker_voices=self._max_speaker_voices(),
            auto_match_speaker_gender=self.gender_match_switch.get() == 1,
            subtitles_enabled=self.subtitle_switch.get() == 1,
            subtitle_language=self._subtitle_code_from_label(self.subtitle_menu.get()),
            retime_video_to_dub=self.retime_switch.get() == 1,
        )
        self.defaults_status.configure(text="Default timing behavior updated.")

    def _max_speaker_voices(self) -> int:
        try:
            return max(1, int(self.max_voices_menu.get()))
        except ValueError:
            return DEFAULT_MAX_SPEAKER_VOICES

    def _update_voice_mode_state(self) -> None:
        per_speaker = self._voice_mode_from_label(self.voice_mode_menu.get()) == "per_speaker"
        self.max_voices_menu.configure(state="normal" if per_speaker else "disabled")
        self.gender_match_switch.configure(state="normal" if per_speaker else "disabled")
        if per_speaker:
            self.experimental_warning.grid()
            self.gender_match_help.configure(text_color=TEXT_MUTED)
        else:
            self.experimental_warning.grid_remove()
            self.gender_match_help.configure(text_color="#63758a")

    def refresh(self, settings, paths, installed_summary: dict[str, object]) -> None:
        self._refreshing = True
        try:
            self.mode_value.set_value("Dark")
            self.settings_path_value.set_value(str(paths.settings_file))
            self.source_menu.set(LANGUAGE_LABELS[settings.default_source_language])
            self.target_menu.set(LANGUAGE_LABELS[settings.default_target_language])
            self.voice_mode_menu.set(VOICE_MODE_LABELS.get(settings.default_voice_mode, VOICE_MODE_LABELS["single"]))
            self.max_voices_menu.set(str(settings.default_max_speaker_voices))
            if settings.auto_match_speaker_gender:
                self.gender_match_switch.select()
            else:
                self.gender_match_switch.deselect()
            if settings.subtitles_enabled:
                self.subtitle_switch.select()
            else:
                self.subtitle_switch.deselect()
            self.subtitle_menu.set(_subtitle_label_for_code(settings.default_subtitle_language))
            self.subtitle_menu.configure(state="normal" if settings.subtitles_enabled else "disabled")
            if settings.retime_video_to_dub:
                self.retime_switch.select()
            else:
                self.retime_switch.deselect()
            self.path_rows["ffmpeg"].set_value(settings.ffmpeg_path or "Not configured")
            self.path_rows["ffprobe"].set_value(settings.ffprobe_path or "Not configured")
            self.path_rows["logs"].set_value(str(paths.logs))
            self.path_rows["models"].set_value(str(paths.models))
            self.path_rows["projects"].set_value(str(paths.projects))
            self.path_rows["exports"].set_value(str(paths.exports))
            self.install_text.delete("1.0", "end")
            self.install_text.insert("end", json.dumps(installed_summary, indent=2))
            self.defaults_status.configure(text="Saved defaults will be used for new sessions.")
        finally:
            self._refreshing = False
        self._update_voice_mode_state()
