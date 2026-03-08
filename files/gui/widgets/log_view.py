"""Scrollable log text widget."""

from __future__ import annotations

import customtkinter as ctk

from files.gui.theme import ui_font


class LogView(ctk.CTkTextbox):
    def __init__(self, master, height: int = 260, max_lines: int = 1200) -> None:
        super().__init__(master, height=height, wrap="word", font=ui_font(11))
        self.max_lines = max_lines
        self._pending_lines: list[str] = []
        self._flush_scheduled = False
        self.configure(state="disabled")

    def append_line(self, line: str) -> None:
        self._pending_lines.append(line.rstrip())
        if not self._flush_scheduled:
            self._flush_scheduled = True
            self.after(80, self._flush_pending_lines)

    def _flush_pending_lines(self) -> None:
        self._flush_scheduled = False
        if not self._pending_lines or not self.winfo_exists():
            return
        text = "\n".join(self._pending_lines) + "\n"
        self._pending_lines.clear()
        self.configure(state="normal")
        self.insert("end", text)
        line_count = int(self.index("end-1c").split(".")[0])
        if line_count > self.max_lines:
            trim_to_line = line_count - self.max_lines
            self.delete("1.0", f"{trim_to_line}.0")
        self.see("end")
        self.configure(state="disabled")

    def clear(self) -> None:
        self._pending_lines.clear()
        self._flush_scheduled = False
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")
