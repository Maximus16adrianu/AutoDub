"""Setup and readiness page."""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from files.core.result_types import EnvironmentSnapshot
from files.gui.status_cards import StatusItemCard
from files.gui.theme import PANEL_COLOR, TEXT_MUTED, ui_font
from files.gui.widgets.section_card import SectionCard


class SetupPage(ctk.CTkScrollableFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.summary_card = SectionCard(
            self,
            "Environment Setup",
            "Review the local runtime in one place. Everything is listed together, and install or repair actions run directly from here.",
        )
        self.summary_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        stats_frame = ctk.CTkFrame(self.summary_card, fg_color="transparent")
        stats_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        for column in range(5):
            stats_frame.grid_columnconfigure(column, weight=1)
        self.summary_values: dict[str, ctk.CTkLabel] = {}
        for column, (key, label_text) in enumerate(
            [
                ("checked_at", "Last check"),
                ("gpu", "GPU"),
                ("cuda", "CUDA"),
                ("cache", "Cache size"),
                ("attention", "Needs attention"),
            ]
        ):
            tile = ctk.CTkFrame(stats_frame, fg_color=PANEL_COLOR, corner_radius=10, border_width=1, border_color="#263244")
            tile.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=0)
            tile.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(tile, text=label_text, text_color=TEXT_MUTED, font=ui_font(11)).grid(
                row=0, column=0, sticky="w", padx=10, pady=(8, 2)
            )
            value_label = ctk.CTkLabel(tile, text="", font=ui_font(12, weight="bold"), anchor="w")
            value_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
            self.summary_values[key] = value_label
        actions = ctk.CTkFrame(self.summary_card, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="w", padx=14, pady=(6, 14))
        ctk.CTkButton(actions, text="Retry check", width=112, height=30, font=ui_font(11), command=self.controller.run_environment_scan).grid(
            row=0, column=0, padx=(0, 10)
        )
        ctk.CTkButton(actions, text="Install missing", width=128, height=30, font=ui_font(11), command=self.controller.install_all_missing).grid(
            row=0, column=1, padx=(0, 10)
        )
        ctk.CTkButton(actions, text="Open models", width=118, height=30, font=ui_font(11), command=self.controller.open_models_folder).grid(
            row=0, column=2, padx=(0, 10)
        )
        ctk.CTkButton(actions, text="Open logs", width=108, height=30, font=ui_font(11), command=self.controller.open_logs_folder).grid(row=0, column=3)
        self.items_card = SectionCard(
            self,
            "Setup Items",
            "Everything is shown as one compact checklist. Each row stays small and keeps its fix actions next to the status.",
        )
        self.items_card.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        self.items_card.grid_columnconfigure(0, weight=1)
        self.cards: list[StatusItemCard] = []

    def _display_timestamp(self, value: str) -> str:
        if not value:
            return "Never"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def refresh_snapshot(self, snapshot: EnvironmentSnapshot | None) -> None:
        if snapshot is None:
            return
        self.summary_values["checked_at"].configure(text=self._display_timestamp(snapshot.checked_at))
        self.summary_values["gpu"].configure(text="Available" if snapshot.gpu_available else "Not available")
        self.summary_values["cuda"].configure(text="Available" if snapshot.cuda_available else "Not available")
        self.summary_values["cache"].configure(text=f"{snapshot.cache_size_mb:.2f} MB")
        attention_count = sum(1 for item in snapshot.items if item.status != "ok")
        self.summary_values["attention"].configure(text="All ready" if attention_count == 0 else f"{attention_count} item(s)")
        for card in self.cards:
            card.destroy()
        self.cards.clear()
        for index, item in enumerate(snapshot.items):
            card = StatusItemCard(self.items_card, self.controller.handle_setup_action)
            card.grid(row=2 + index, column=0, sticky="ew", padx=10, pady=(0, 8))
            card.set_item(item)
            self.cards.append(card)
