"""Processing status page."""

from __future__ import annotations

import time

import customtkinter as ctk

from files.gui.theme import ui_font
from files.gui.widgets.log_view import LogView
from files.gui.widgets.progress_panel import ProgressPanel
from files.gui.widgets.section_card import SectionCard
from files.utils.time_utils import format_seconds


class ProcessingPage(ctk.CTkFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._started_at: float | None = None
        self.header = SectionCard(self, "Processing", "Watch each stage of the dubbing pipeline as it runs.")
        self.header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 16))
        self.job_label = ctk.CTkLabel(self.header, text="No active job.", anchor="w", font=ui_font(12))
        self.job_label.grid(row=2, column=0, sticky="ew", padx=18)
        self.queue_label = ctk.CTkLabel(self.header, text="", anchor="w", font=ui_font(11))
        self.queue_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(4, 0))
        self.elapsed_label = ctk.CTkLabel(self.header, text="Elapsed: 00:00:00", anchor="w", font=ui_font(12))
        self.elapsed_label.grid(row=4, column=0, sticky="ew", padx=18, pady=(4, 16))
        self.progress_panel = ProgressPanel(self)
        self.progress_panel.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=24, pady=(0, 16))
        self.cancel_button = ctk.CTkButton(actions, text="Cancel Job", font=ui_font(12), command=self.controller.cancel_current_job)
        self.cancel_button.grid(row=0, column=0)
        self.status_label = ctk.CTkLabel(actions, text="Idle", font=ui_font(12))
        self.status_label.grid(row=0, column=1, padx=(12, 0))
        self.log_view = LogView(self)
        self.log_view.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))

    def set_job_started(self, job_id: str, queue_text: str = "") -> None:
        self._started_at = time.time()
        self.job_label.configure(text=f"Project: {job_id}")
        self.queue_label.configure(text=queue_text)
        self.status_label.configure(text="Running")
        self.log_view.clear()
        self.progress_panel.update_progress("Preparing project", "Waiting for the pipeline to begin...", 0.0)
        self._tick_elapsed()

    def set_install_started(self, title: str, queue_text: str = "") -> None:
        self._started_at = time.time()
        self.job_label.configure(text=f"Setup task: {title}")
        self.queue_label.configure(text=queue_text)
        self.status_label.configure(text="Installing")
        self.log_view.clear()
        self.progress_panel.update_progress(f"Installing {title}", "Preparing install task...", 0.0)
        self._tick_elapsed()

    def update_stage(self, stage: str, detail: str, progress: float | None) -> None:
        self.progress_panel.update_progress(stage, detail, progress)

    def append_log(self, line: str) -> None:
        self.log_view.append_line(line)

    def set_finished(self, message: str) -> None:
        self.status_label.configure(text=message)
        self.progress_panel.update_progress(self.progress_panel.stage_label.cget("text"), self.progress_panel.detail_label.cget("text"), 1.0)

    def set_failed(self, message: str) -> None:
        self.status_label.configure(text=message)

    def set_queue_text(self, queue_text: str) -> None:
        self.queue_label.configure(text=queue_text)

    def current_progress(self) -> float:
        return self.progress_panel.current_progress()

    def _tick_elapsed(self) -> None:
        if self._started_at is None:
            return
        self.elapsed_label.configure(text=f"Elapsed: {format_seconds(time.time() - self._started_at)}")
        if self.status_label.cget("text") in {"Running", "Installing"}:
            self.after(1000, self._tick_elapsed)
