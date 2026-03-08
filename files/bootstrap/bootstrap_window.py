"""Fallback tkinter bootstrap UI."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from tkinter import scrolledtext, ttk

from files.bootstrap.dependency_check import StartupCheckResult
from files.bootstrap.installer import RequirementsInstaller


SURFACE = "#0f141b"
CARD = "#171f29"
CARD_ELEVATED = "#1d2733"
CARD_BORDER = "#2a3645"
TEXT = "#e6edf3"
TEXT_MUTED = "#9fb0c3"
ACCENT = "#1aa0b8"
ACCENT_HOVER = "#12879b"
SUCCESS = "#2f9e44"
WARNING = "#f08c00"
ERROR = "#e03131"
BUTTON_MUTED = "#243140"
BUTTON_MUTED_HOVER = "#2e3d4f"
LOG_BG = "#0b1117"


class BootstrapWindow:
    def __init__(
        self,
        *,
        paths,
        startup_result: StartupCheckResult,
        installer: RequirementsInstaller,
        launch_callback,
    ) -> None:
        self.paths = paths
        self.startup_result = startup_result
        self.installer = installer
        self.launch_callback = launch_callback
        self.queue: Queue[tuple[str, str]] = Queue()
        self.install_running = False
        self.root = tk.Tk()
        self.root.title("AutoDub Studio Setup")
        self.root.geometry("1080x760")
        self.root.minsize(980, 700)
        self.root.configure(bg=SURFACE)
        self._configure_styles()
        self._prepare_log_file()
        self._build()
        self._render_summary()
        self.root.after(120, self._poll_queue)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Bootstrap.Horizontal.TProgressbar",
            troughcolor=CARD,
            background=ACCENT,
            bordercolor=CARD,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=10,
        )

    def _prepare_log_file(self) -> None:
        self.paths.bootstrap_log.parent.mkdir(parents=True, exist_ok=True)
        self.paths.bootstrap_log.write_text("", encoding="utf-8")

    def _build(self) -> None:
        outer = tk.Frame(self.root, bg=SURFACE)
        outer.pack(fill="both", expand=True, padx=28, pady=26)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(3, weight=1)

        header = self._card(outer, elevated=True, pady=24, padx=24)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        header_text = tk.Frame(header, bg=CARD_ELEVATED)
        header_text.grid(row=0, column=0, sticky="w")
        tk.Label(
            header_text,
            text="AutoDub Studio",
            font=("Segoe UI Semibold", 24),
            bg=CARD_ELEVATED,
            fg=TEXT,
        ).pack(anchor="w")
        tk.Label(
            header_text,
            text="Bootstrap setup",
            font=("Segoe UI Semibold", 12),
            bg=CARD_ELEVATED,
            fg=ACCENT,
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            header_text,
            text=(
                "The launcher can come up before the full stack is installed. "
                "Use this window to review what is missing, install Python dependencies, "
                "and then reopen the full CustomTkinter application automatically."
            ),
            font=("Segoe UI", 10),
            bg=CARD_ELEVATED,
            fg=TEXT_MUTED,
            justify="left",
            wraplength=700,
        ).pack(anchor="w", pady=(10, 0))

        badge_wrap = tk.Frame(header, bg=CARD_ELEVATED)
        badge_wrap.grid(row=0, column=1, sticky="ne", padx=(16, 0))
        self.status_badge = tk.Label(
            badge_wrap,
            text="",
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=7,
            bg=BUTTON_MUTED,
            fg="white",
        )
        self.status_badge.pack(anchor="e")

        top_grid = tk.Frame(outer, bg=SURFACE)
        top_grid.grid(row=1, column=0, sticky="nsew", pady=(20, 20))
        top_grid.grid_columnconfigure(0, weight=1)
        top_grid.grid_columnconfigure(1, weight=1)

        self.overview_card = self._card(top_grid)
        self.overview_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._card_header(
            self.overview_card,
            "Environment overview",
            "These checks are lightweight and safe to run before the heavy runtime is installed.",
        )
        self.overview_rows = tk.Frame(self.overview_card, bg=CARD)
        self.overview_rows.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        right_column = tk.Frame(top_grid, bg=SURFACE)
        right_column.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_column.grid_rowconfigure(0, weight=1)

        self.missing_card = self._card(right_column)
        self.missing_card.grid(row=0, column=0, sticky="nsew")
        self._card_header(
            self.missing_card,
            "Missing or pending items",
            "Only Python package installation happens here. FFmpeg, models, and voices can be completed later inside the main app.",
        )
        self.missing_items_frame = tk.Frame(self.missing_card, bg=CARD)
        self.missing_items_frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        action_row = self._card(outer, pady=18, padx=18)
        action_row.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        action_row.grid_columnconfigure(0, weight=1)
        action_row.grid_columnconfigure(1, weight=0)
        action_text = tk.Frame(action_row, bg=CARD)
        action_text.grid(row=0, column=0, sticky="w")
        self.action_title_label = tk.Label(
            action_text,
            text=self.startup_result.status_title,
            font=("Segoe UI Semibold", 14),
            bg=CARD,
            fg=TEXT,
        )
        self.action_title_label.pack(anchor="w")
        self.action_message_label = tk.Label(
            action_text,
            text=self.startup_result.status_message,
            font=("Segoe UI", 10),
            bg=CARD,
            fg=TEXT_MUTED,
            justify="left",
            wraplength=540,
        )
        self.action_message_label.pack(anchor="w", pady=(6, 0))

        actions = tk.Frame(action_row, bg=CARD)
        actions.grid(row=0, column=1, sticky="e")
        install_label = "Install now" if self.startup_result.missing_packages else "Reinstall packages"
        self.install_button = self._button(
            actions,
            text=install_label,
            command=self._start_install,
            bg=ACCENT,
            hover_bg=ACCENT_HOVER,
            width=160,
        )
        self.install_button.grid(row=0, column=0, padx=(0, 10))
        self.open_logs_button = self._button(
            actions,
            text="Open log folder",
            command=lambda: os.startfile(str(self.paths.logs)),
            bg=BUTTON_MUTED,
            hover_bg=BUTTON_MUTED_HOVER,
            width=150,
        )
        self.open_logs_button.grid(row=0, column=1, padx=(0, 10))
        self.exit_button = self._button(
            actions,
            text="Exit",
            command=self.root.destroy,
            bg=BUTTON_MUTED,
            hover_bg=BUTTON_MUTED_HOVER,
            width=100,
        )
        self.exit_button.grid(row=0, column=2)

        progress_row = tk.Frame(action_row, bg=CARD)
        progress_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        progress_row.grid_columnconfigure(0, weight=1)
        self.progress_label = tk.Label(
            progress_row,
            text="Waiting for action.",
            font=("Segoe UI", 10),
            bg=CARD,
            fg=TEXT_MUTED,
        )
        self.progress_label.grid(row=0, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(progress_row, style="Bootstrap.Horizontal.TProgressbar", mode="indeterminate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        log_card = self._card(outer, elevated=True)
        log_card.grid(row=3, column=0, sticky="nsew")
        self._card_header(
            log_card,
            "Install log",
            "Package installation output is streamed live from pip. Detailed traces are also written to data/logs/bootstrap-install.log.",
        )
        self.log_text = scrolledtext.ScrolledText(
            log_card,
            height=18,
            bg=LOG_BG,
            fg="#d7e3ee",
            insertbackground="#d7e3ee",
            relief="flat",
            padx=14,
            pady=12,
            font=("Cascadia Mono", 10),
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER,
            borderwidth=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.footer_label = tk.Label(
            outer,
            text="",
            font=("Segoe UI", 10),
            bg=SURFACE,
            fg=TEXT_MUTED,
            anchor="w",
        )
        self.footer_label.grid(row=4, column=0, sticky="ew", pady=(16, 0))

        if not self.startup_result.install_allowed:
            self.install_button.configure(state="disabled", cursor="arrow", bg="#4c5969")

    def _card(self, parent, *, elevated: bool = False, padx: int = 20, pady: int = 20) -> tk.Frame:
        background = CARD_ELEVATED if elevated else CARD
        frame = tk.Frame(
            parent,
            bg=background,
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            bd=0,
            padx=padx,
            pady=pady,
        )
        return frame

    def _card_header(self, parent: tk.Frame, title: str, subtitle: str) -> None:
        bg = parent.cget("bg")
        tk.Label(parent, text=title, font=("Segoe UI Semibold", 15), bg=bg, fg=TEXT).pack(anchor="w")
        tk.Label(
            parent,
            text=subtitle,
            font=("Segoe UI", 10),
            bg=bg,
            fg=TEXT_MUTED,
            justify="left",
            wraplength=440,
        ).pack(anchor="w", pady=(6, 16))

    def _button(self, parent, *, text: str, command, bg: str, hover_bg: str, width: int) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            width=width // 10,
            bg=bg,
            fg="white",
            activebackground=hover_bg,
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=10,
        )
        return button

    def _render_summary(self) -> None:
        if not self.startup_result.python_ok:
            tone = "error"
        elif self.startup_result.missing_packages:
            tone = "warning"
        else:
            tone = "success"
        self._set_status_badge(self.startup_result.status_title, tone)
        self.action_title_label.configure(text=self.startup_result.status_title)
        self.action_message_label.configure(text=self.startup_result.status_message)

        for child in self.overview_rows.winfo_children():
            child.destroy()
        summary_rows = [
            ("Python", f"{self.startup_result.current_python_version}", SUCCESS if self.startup_result.python_ok else ERROR),
            (
                "Python packages",
                "Ready" if not self.startup_result.missing_packages else f"{len(self.startup_result.missing_packages)} missing",
                SUCCESS if not self.startup_result.missing_packages else WARNING,
            ),
            ("FFmpeg", "Detected" if self.startup_result.ffmpeg_found else "Not found on PATH", SUCCESS if self.startup_result.ffmpeg_found else WARNING),
            (
                "ffprobe",
                "Detected" if self.startup_result.ffprobe_found else "Not found on PATH",
                SUCCESS if self.startup_result.ffprobe_found else WARNING,
            ),
            (
                "WhisperX assets",
                "Prepared" if self.startup_result.whisperx_model_prepared else "Pending main-app setup",
                SUCCESS if self.startup_result.whisperx_model_prepared else WARNING,
            ),
            (
                "Piper runtime",
                "Installed" if self.startup_result.piper_runtime_prepared else "Pending main-app setup",
                SUCCESS if self.startup_result.piper_runtime_prepared else WARNING,
            ),
            (
                "Piper voices",
                f"{self.startup_result.piper_voice_count} installed" if self.startup_result.piper_voice_count else "Pending main-app setup",
                SUCCESS if self.startup_result.piper_voice_count else WARNING,
            ),
        ]
        for index, (title, value, accent) in enumerate(summary_rows):
            row = tk.Frame(self.overview_rows, bg=CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=title, font=("Segoe UI Semibold", 10), bg=CARD, fg=TEXT).pack(side="left")
            tk.Label(
                row,
                text=value,
                font=("Segoe UI", 10),
                bg=CARD,
                fg=accent,
                anchor="e",
            ).pack(side="right")
            if index < len(summary_rows) - 1:
                divider = tk.Frame(self.overview_rows, bg=CARD_BORDER, height=1)
                divider.pack(fill="x", pady=(4, 2))

        for child in self.missing_items_frame.winfo_children():
            child.destroy()
        missing_items = self.startup_result.missing_items
        if not missing_items:
            success_card = tk.Frame(
                self.missing_items_frame,
                bg="#10291a",
                highlightthickness=1,
                highlightbackground="#1f6f35",
                padx=14,
                pady=14,
            )
            success_card.pack(fill="x")
            tk.Label(
                success_card,
                text="Nothing blocking package launch right now. If the main app still failed previously, you can reinstall dependencies from here.",
                bg="#10291a",
                fg="#d8f5df",
                justify="left",
                wraplength=390,
                font=("Segoe UI", 10),
            ).pack(anchor="w")
        else:
            for item in missing_items:
                item_card = tk.Frame(
                    self.missing_items_frame,
                    bg=CARD_ELEVATED,
                    highlightthickness=1,
                    highlightbackground=CARD_BORDER,
                    padx=12,
                    pady=12,
                )
                item_card.pack(fill="x", pady=(0, 10))
                tk.Label(item_card, text="•", font=("Segoe UI Semibold", 14), bg=CARD_ELEVATED, fg=ACCENT).pack(
                    side="left", anchor="n"
                )
                tk.Label(
                    item_card,
                    text=item,
                    bg=CARD_ELEVATED,
                    fg=TEXT,
                    justify="left",
                    wraplength=360,
                    font=("Segoe UI", 10),
                ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        footer_lines = self.startup_result.notes or ["Bootstrap launcher is ready."]
        self.footer_label.configure(text=footer_lines[-1])
        self._append_log("Bootstrap launcher ready.")
        for note in footer_lines:
            self._append_log(note)

    def _set_status_badge(self, text: str, tone: str = "neutral") -> None:
        colors = {
            "neutral": BUTTON_MUTED,
            "info": ACCENT,
            "success": SUCCESS,
            "warning": WARNING,
            "error": ERROR,
        }
        self.status_badge.configure(text=text, bg=colors.get(tone, BUTTON_MUTED))

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        with self.paths.bootstrap_log.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")

    def _start_install(self) -> None:
        if self.install_running or not self.startup_result.install_allowed:
            return
        self.install_running = True
        self.install_button.configure(state="disabled", cursor="arrow", bg="#4c5969")
        self.progress_label.configure(text="Installing Python dependencies with pip...")
        self._set_status_badge("Installing", "info")
        self._append_log("Starting package installation from requirements.txt.")
        self.progress_bar.start(10)

        def worker() -> None:
            try:
                self.installer.install(lambda line: self.queue.put(("log", line)))
            except Exception as exc:
                self.queue.put(("error", str(exc)))
                return
            self.queue.put(("success", "Dependencies installed successfully. Relaunching AutoDub Studio..."))

        threading.Thread(target=worker, name="bootstrap-install", daemon=True).start()

    def _finish_install(self, *, success: bool, message: str) -> None:
        self.install_running = False
        self.progress_bar.stop()
        self.progress_label.configure(text=message)
        if success:
            self._set_status_badge("Ready to launch", "success")
            self.footer_label.configure(text="The full CustomTkinter application will reopen automatically.")
        else:
            self._set_status_badge("Install failed", "error")
            self.footer_label.configure(text="Installation failed. Review the log output and try again.")
            if self.startup_result.install_allowed:
                self.install_button.configure(state="normal", cursor="hand2", bg=ACCENT)

    def _poll_queue(self) -> None:
        while True:
            try:
                event_type, payload = self.queue.get_nowait()
            except Empty:
                break
            if event_type == "log":
                self._append_log(payload)
            elif event_type == "error":
                self._append_log(payload)
                self._finish_install(success=False, message="Package installation did not complete successfully.")
            elif event_type == "success":
                self._append_log(payload)
                self._finish_install(success=True, message="Installation finished. Starting the main app...")
                self.root.after(900, self._launch_and_close)
        self.root.after(120, self._poll_queue)

    def _launch_and_close(self) -> None:
        self.launch_callback()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
