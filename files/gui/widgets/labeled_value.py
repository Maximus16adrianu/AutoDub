"""Label/value row widget."""

from __future__ import annotations

import customtkinter as ctk

from files.gui.theme import TEXT_MUTED, ui_font


class LabeledValue(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.label = ctk.CTkLabel(self, text=label, text_color=TEXT_MUTED, font=ui_font(12))
        self.label.grid(row=0, column=0, sticky="w")
        self.value = ctk.CTkLabel(self, text=value, anchor="w", justify="left", wraplength=440, font=ui_font(12))
        self.value.grid(row=0, column=1, sticky="ew", padx=(12, 0))

    def set_value(self, value: str) -> None:
        self.value.configure(text=value)
