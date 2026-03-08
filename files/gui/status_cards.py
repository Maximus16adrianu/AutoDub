"""Reusable status card widgets."""

from __future__ import annotations

import customtkinter as ctk

from files.core.result_types import EnvironmentStatusItem
from files.gui.theme import CARD_COLOR, ERROR_COLOR, PANEL_COLOR, SUCCESS_COLOR, TEXT_MUTED, WARNING_COLOR, ui_font


STATUS_COLORS = {
    "ok": SUCCESS_COLOR,
    "missing": WARNING_COLOR,
    "error": ERROR_COLOR,
    "busy": "#1971c2",
}


class StatusItemCard(ctk.CTkFrame):
    def __init__(self, master, action_callback) -> None:
        super().__init__(master, corner_radius=10, fg_color=CARD_COLOR, border_width=1, border_color="#263244")
        self.action_callback = action_callback
        self.item: EnvironmentStatusItem | None = None
        self.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(header, text="", font=ui_font(14, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        self.status_label = ctk.CTkLabel(
            header,
            text="",
            corner_radius=999,
            fg_color=PANEL_COLOR,
            font=ui_font(11, weight="bold"),
            padx=9,
            pady=2,
        )
        self.status_label.grid(row=0, column=1, sticky="e")
        self.description_label = ctk.CTkLabel(
            self,
            text="",
            justify="left",
            wraplength=1000,
            anchor="w",
            font=ui_font(11),
        )
        self.description_label.grid(row=1, column=0, sticky="ew", padx=12)
        self.details_label = ctk.CTkLabel(
            self,
            text="",
            justify="left",
            text_color=TEXT_MUTED,
            wraplength=1000,
            anchor="w",
            font=ui_font(10),
        )
        self.details_label.grid(row=2, column=0, sticky="ew", padx=12, pady=(3, 0))
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=3, column=0, sticky="w", padx=12, pady=(7, 10))

    def _compact_details(self, text: str, limit: int = 110) -> str:
        if len(text) <= limit:
            return text
        head = max(24, limit // 2 - 4)
        tail = max(24, limit - head - 3)
        return f"{text[:head]}...{text[-tail:]}"

    def set_item(self, item: EnvironmentStatusItem) -> None:
        self.item = item
        self.title_label.configure(text=item.title)
        self.status_label.configure(text=item.status.upper(), fg_color=STATUS_COLORS[item.status], text_color="white")
        self.description_label.configure(text=item.description)
        if item.details:
            self.details_label.configure(text=self._compact_details(item.details))
            self.details_label.grid()
        else:
            self.details_label.configure(text="")
            self.details_label.grid_remove()
        for child in self.action_frame.winfo_children():
            child.destroy()
        for index, action in enumerate(item.actions):
            button = ctk.CTkButton(
                self.action_frame,
                text=action,
                width=126,
                height=28,
                font=ui_font(11),
                command=lambda action_name=action: self._invoke_action(action_name),
            )
            button.grid(row=0, column=index, padx=(0, 8), pady=(0, 0), sticky="w")
        if item.actions:
            self.action_frame.grid()
        else:
            self.action_frame.grid_remove()

    def _invoke_action(self, action_name: str) -> None:
        if self.item is not None:
            self.action_callback(self.item, action_name)
