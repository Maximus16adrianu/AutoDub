"""Processing progress widget."""

from __future__ import annotations

import customtkinter as ctk

from files.gui.theme import TEXT_MUTED, ui_font


class ProgressPanel(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._progress_value = 0.0
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.stage_label = ctk.CTkLabel(header, text="Idle", font=ui_font(18, weight="bold"))
        self.stage_label.grid(row=0, column=0, sticky="w")
        self.percent_label = ctk.CTkLabel(header, text="0%", text_color=TEXT_MUTED, font=ui_font(12, weight="bold"))
        self.percent_label.grid(row=0, column=1, sticky="e")
        self.detail_label = ctk.CTkLabel(self, text="Waiting for a job.", text_color=TEXT_MUTED, anchor="w", font=ui_font(12))
        self.detail_label.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=2, column=0, sticky="ew")
        self.progress_bar.set(0)

    def update_progress(self, stage: str, detail: str, progress: float | None) -> None:
        self.stage_label.configure(text=stage)
        self.detail_label.configure(text=detail)
        if progress is not None:
            self._progress_value = max(0.0, min(1.0, progress))
            self.progress_bar.set(self._progress_value)
            self.percent_label.configure(text=f"{self._progress_value * 100:.0f}%")

    def current_progress(self) -> float:
        return self._progress_value
