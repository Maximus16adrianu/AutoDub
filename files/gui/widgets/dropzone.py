"""Button-based file picker panel."""

from __future__ import annotations

import customtkinter as ctk

from files.gui.theme import PANEL_COLOR, TEXT_MUTED, ui_font


class Dropzone(ctk.CTkFrame):
    def __init__(self, master, pick_callback) -> None:
        super().__init__(master, corner_radius=18, fg_color=PANEL_COLOR, border_width=1, border_color="#263244")
        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self, text="Choose a video file to dub", font=ui_font(20, weight="bold"))
        self.label.grid(row=0, column=0, pady=(24, 8), padx=18)
        self.caption = ctk.CTkLabel(
            self,
            text="Use the button below to select a local video. The app keeps all derived outputs inside a managed project folder.",
            text_color=TEXT_MUTED,
            wraplength=640,
            justify="center",
            font=ui_font(12),
        )
        self.caption.grid(row=1, column=0, pady=(0, 16), padx=18)
        self.button = ctk.CTkButton(self, text="Select Video", width=180, height=42, command=pick_callback, font=ui_font(12))
        self.button.grid(row=2, column=0, pady=(0, 24))
