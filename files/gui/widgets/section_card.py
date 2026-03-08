"""Section card widget."""

from __future__ import annotations

import customtkinter as ctk

from files.gui.theme import CARD_COLOR, TEXT_MUTED, ui_font


class SectionCard(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = "") -> None:
        super().__init__(master, corner_radius=16, fg_color=CARD_COLOR, border_width=1, border_color="#263244")
        self.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(self, text=title, font=ui_font(18, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w", padx=14, pady=(13, 3))
        self.subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle,
            text_color=TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=980,
            font=ui_font(12),
        )
        self.subtitle_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 13))
