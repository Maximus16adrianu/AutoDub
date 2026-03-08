"""Export summary page."""

from __future__ import annotations

import customtkinter as ctk

from files.core.result_types import JobResult
from files.gui.theme import ui_font
from files.gui.widgets.labeled_value import LabeledValue
from files.gui.widgets.section_card import SectionCard


class ExportPage(ctk.CTkFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.card = SectionCard(
            self,
            "Exports",
            "Open the generated outputs or copy their paths. When subtitles are enabled, they are burned into the final video and also exported as a separate SRT file.",
        )
        self.card.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 16))
        self.rows = {
            "dubbed_video": LabeledValue(self.card, "Dubbed video"),
            "transcript_json": LabeledValue(self.card, "Transcript JSON"),
            "words_json": LabeledValue(self.card, "Words JSON"),
            "translated_segments_json": LabeledValue(self.card, "Translated segments JSON"),
            "subtitles_srt": LabeledValue(self.card, "Subtitle SRT"),
            "project_folder": LabeledValue(self.card, "Project folder"),
        }
        for index, widget in enumerate(self.rows.values(), start=2):
            widget.grid(row=index, column=0, sticky="ew", padx=18, pady=4)
        actions = ctk.CTkFrame(self.card, fg_color="transparent")
        actions.grid(row=8, column=0, sticky="w", padx=18, pady=(12, 18))
        self.open_project_button = ctk.CTkButton(actions, text="Open project folder", font=ui_font(12), command=self.controller.open_project_folder)
        self.open_project_button.grid(row=0, column=0, padx=(0, 10))
        self.copy_path_button = ctk.CTkButton(
            actions,
            text="Copy dubbed video path",
            font=ui_font(12),
            command=lambda: self.controller.copy_output_path("dubbed_video"),
        )
        self.copy_path_button.grid(row=0, column=1)
        self.empty_state = ctk.CTkLabel(
            self.card,
            text="No export bundle is available yet. Run a dubbing job to populate this page.",
            justify="left",
            wraplength=640,
            font=ui_font(12),
        )
        self.empty_state.grid(row=9, column=0, sticky="w", padx=18, pady=(0, 18))
        self._set_action_state(False)

    def _set_action_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.open_project_button.configure(state=state)
        self.copy_path_button.configure(state=state)

    def load_result(self, result: JobResult | None) -> None:
        if result is None:
            for widget in self.rows.values():
                widget.set_value("Not available yet")
            self.empty_state.configure(text="No export bundle is available yet. Run a dubbing job to populate this page.")
            self._set_action_state(False)
            return
        self.rows["dubbed_video"].set_value(str(result.output_paths.dubbed_video))
        self.rows["transcript_json"].set_value(str(result.output_paths.transcript_json))
        self.rows["words_json"].set_value(str(result.output_paths.words_json))
        self.rows["translated_segments_json"].set_value(str(result.output_paths.translated_segments_json))
        self.rows["subtitles_srt"].set_value(str(result.output_paths.subtitles_srt) if result.output_paths.subtitles_srt else "Disabled for this job")
        self.rows["project_folder"].set_value(str(result.output_paths.project_folder))
        self.empty_state.configure(text="Latest job outputs are listed above.")
        self._set_action_state(True)
