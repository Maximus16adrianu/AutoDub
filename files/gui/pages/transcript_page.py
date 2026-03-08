"""Transcript inspection page."""

from __future__ import annotations

import customtkinter as ctk

from files.core.result_types import JobResult
from files.gui.theme import ACCENT_COLOR
from files.gui.theme import CARD_COLOR, PANEL_COLOR, TEXT_MUTED, ui_font
from files.gui.widgets.section_card import SectionCard
from files.stt.schemas import TranscriptSegment
from files.utils.time_utils import format_seconds


TRANSCRIPT_RENDER_BATCH_SIZE = 18
TRANSCRIPT_SEARCH_DEBOUNCE_MS = 180


class TranscriptPage(ctk.CTkFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self._result: JobResult | None = None
        self._loaded_job_id: str | None = None
        self._render_after_id: str | None = None
        self._search_after_id: str | None = None
        self._render_token = 0
        self._pending_segments: list[tuple[TranscriptSegment, str]] = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = SectionCard(self, "Transcript", "Inspect source and translated segments with timestamps and speaker labels.")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 16))
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        controls.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(controls, placeholder_text="Search transcript", font=ui_font(12))
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda _event: self._schedule_refresh())
        self.export_transcript_button = ctk.CTkButton(
            controls,
            text="Export transcript JSON",
            font=ui_font(12),
            command=self.controller.export_transcript_json,
        )
        self.export_transcript_button.grid(row=0, column=1, padx=(0, 10))
        self.export_words_button = ctk.CTkButton(controls, text="Export words JSON", font=ui_font(12), command=self.controller.export_words_json)
        self.export_words_button.grid(row=0, column=2, padx=(0, 10))
        self.export_srt_button = ctk.CTkButton(controls, text="Export SRT", font=ui_font(12), command=self.controller.export_srt)
        self.export_srt_button.grid(row=0, column=3)
        self.render_status_label = ctk.CTkLabel(controls, text="", text_color=TEXT_MUTED, font=ui_font(11))
        self.render_status_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        header_row = ctk.CTkFrame(self, fg_color=PANEL_COLOR, corner_radius=14)
        header_row.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 10))
        header_row.grid_columnconfigure(0, weight=1)
        header_row.grid_columnconfigure(1, weight=1)
        header_row.grid_columnconfigure(2, weight=1)
        header_row.grid_columnconfigure(3, weight=1)
        header_row.grid_columnconfigure(4, weight=4)
        header_row.grid_columnconfigure(5, weight=4)
        headers = ["Speaker", "Start", "End", "Duration", "Source text", "Translated text"]
        for index, title in enumerate(headers):
            ctk.CTkLabel(
                header_row,
                text=title,
                font=ui_font(12, weight="bold"),
                text_color=TEXT_MUTED,
            ).grid(row=0, column=index, sticky="w", padx=14, pady=12)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self.body.grid_columnconfigure(0, weight=1)
        self._set_action_state(False)
        self.bind("<Destroy>", self._on_destroy)

    def load_result(self, result: JobResult | None) -> None:
        job_id = result.job_id if result else None
        if job_id == self._loaded_job_id and result is self._result:
            return
        self._result = result
        self._loaded_job_id = job_id
        self._set_action_state(result is not None, bool(result and result.output_paths.subtitles_srt))
        self._refresh_rows()

    def _set_action_state(self, enabled: bool, srt_enabled: bool = False) -> None:
        state = "normal" if enabled else "disabled"
        self.export_transcript_button.configure(state=state)
        self.export_words_button.configure(state=state)
        self.export_srt_button.configure(state="normal" if srt_enabled else "disabled")

    def _on_destroy(self, _event) -> None:
        if not self.winfo_exists():
            self._cancel_scheduled_work()

    def _cancel_scheduled_work(self) -> None:
        if self._render_after_id is not None:
            try:
                self.after_cancel(self._render_after_id)
            except Exception:
                pass
            self._render_after_id = None
        if self._search_after_id is not None:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
            self._search_after_id = None
        self._render_token += 1

    def _schedule_refresh(self) -> None:
        if self._search_after_id is not None:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.after(TRANSCRIPT_SEARCH_DEBOUNCE_MS, self._refresh_rows)

    def _refresh_rows(self) -> None:
        self._cancel_scheduled_work()
        for child in self.body.winfo_children():
            child.destroy()
        if self._result is None:
            empty = ctk.CTkLabel(self.body, text="No transcript available yet.", text_color=TEXT_MUTED, font=ui_font(12))
            empty.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            self.render_status_label.configure(text="")
            return

        query = self.search_entry.get().strip().lower()
        filtered_segments: list[tuple[TranscriptSegment, str]] = []
        for segment in self._result.transcript.segments:
            translated = segment.translated_text or ""
            searchable = " ".join([segment.text, translated, segment.speaker or ""]).lower()
            if query and query not in searchable:
                continue
            filtered_segments.append((segment, translated))

        if not filtered_segments:
            empty = ctk.CTkLabel(self.body, text="No transcript segments match the current search.", text_color=TEXT_MUTED, font=ui_font(12))
            empty.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            self.render_status_label.configure(text="No matching segments.")
            return

        self._pending_segments = filtered_segments
        token = self._render_token
        self.render_status_label.configure(text=f"Rendering 0 / {len(filtered_segments)} segments...", text_color=ACCENT_COLOR)
        self._render_next_batch(0, token)

    def _render_next_batch(self, start_index: int, token: int) -> None:
        if token != self._render_token or not self.winfo_exists():
            return
        total = len(self._pending_segments)
        end_index = min(start_index + TRANSCRIPT_RENDER_BATCH_SIZE, total)
        for row_index in range(start_index, end_index):
            segment, translated = self._pending_segments[row_index]
            self._create_row(row_index, segment, translated)
        self.render_status_label.configure(text=f"Rendering {end_index} / {total} segments...", text_color=ACCENT_COLOR)
        if end_index >= total:
            self.render_status_label.configure(text=f"Showing {total} segment(s).", text_color=TEXT_MUTED)
            self._render_after_id = None
            return
        self._render_after_id = self.after(12, lambda next_index=end_index, next_token=token: self._render_next_batch(next_index, next_token))

    def _create_row(self, row_index: int, segment: TranscriptSegment, translated: str) -> None:
        row_color = CARD_COLOR if row_index % 2 == 0 else PANEL_COLOR
        row = ctk.CTkFrame(self.body, corner_radius=14, fg_color=row_color, border_width=1, border_color="#263244")
        row.grid(row=row_index, column=0, sticky="ew", pady=(0, 10))
        for column, weight in enumerate((1, 1, 1, 1, 4, 4)):
            row.grid_columnconfigure(column, weight=weight)
        values = [
            segment.speaker or "Single",
            format_seconds(segment.start),
            format_seconds(segment.end),
            f"{segment.duration:.2f}s",
            segment.text,
            translated,
        ]
        wraplengths = [100, 80, 80, 90, 360, 360]
        for column, value in enumerate(values):
            ctk.CTkLabel(
                row,
                text=value,
                anchor="w",
                justify="left",
                wraplength=wraplengths[column],
                font=ui_font(12),
            ).grid(row=0, column=column, sticky="ew", padx=14, pady=12)
