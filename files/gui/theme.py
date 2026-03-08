"""GUI theme helpers."""

from __future__ import annotations

import customtkinter as ctk


PANEL_COLOR = "#161b22"
CARD_COLOR = "#1f2733"
ACCENT_COLOR = "#15aabf"
SUCCESS_COLOR = "#2f9e44"
WARNING_COLOR = "#f08c00"
ERROR_COLOR = "#e03131"
TEXT_MUTED = "#94a3b8"
WIDGET_SCALING = 0.88
WINDOW_SCALING = 0.92
TEXT_SCALE = 1.5


def ui_font(size: int, **kwargs) -> ctk.CTkFont:
    return ctk.CTkFont(size=max(1, int(round(size * TEXT_SCALE))), **kwargs)


def apply_theme(appearance_mode: str) -> None:
    ctk.set_appearance_mode(appearance_mode)
    ctk.set_default_color_theme("dark-blue")
    ctk.set_widget_scaling(WIDGET_SCALING)
    ctk.set_window_scaling(WINDOW_SCALING)
