"""Dialog helpers."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from files.constants import DEFAULT_WHISPERX_MODEL, SUPPORTED_WHISPERX_MODELS, VIDEO_EXTENSIONS, WHISPERX_MODEL_PRESETS
from files.gui.theme import CARD_COLOR, ERROR_COLOR, SUCCESS_COLOR, TEXT_MUTED, WARNING_COLOR, ui_font
from files.utils.file_utils import open_in_explorer


class ModalMessageDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        title_text: str,
        message: str,
        accent_color: str,
        buttons: list[tuple[str, bool]],
    ) -> None:
        super().__init__(master)
        self.result = False
        self.title(title_text)
        self.transient(master)
        self.resizable(False, False)
        self.configure(fg_color="#0f141b")
        self.geometry(self._dialog_geometry(master))
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", lambda: self._close(False))

        shell = ctk.CTkFrame(self, corner_radius=20, fg_color=CARD_COLOR, border_width=1, border_color="#263244")
        shell.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)

        banner = ctk.CTkFrame(shell, corner_radius=14, fg_color=accent_color, height=8)
        banner.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 0))
        title_label = ctk.CTkLabel(shell, text=title_text, font=ui_font(20, weight="bold"))
        title_label.grid(row=1, column=0, sticky="w", padx=18, pady=(16, 6))
        message_label = ctk.CTkLabel(
            shell,
            text=message,
            justify="left",
            anchor="w",
            wraplength=420,
            text_color=TEXT_MUTED,
            font=ui_font(12),
        )
        message_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))

        button_row = ctk.CTkFrame(shell, fg_color="transparent")
        button_row.grid(row=3, column=0, sticky="e", padx=18, pady=(0, 18))
        for index, (label, value) in enumerate(buttons):
            fg_color = accent_color if value else "#233040"
            hover_color = accent_color if value else "#314359"
            button = ctk.CTkButton(
                button_row,
                text=label,
                width=110,
                fg_color=fg_color,
                hover_color=hover_color,
                font=ui_font(12),
                command=lambda result=value: self._close(result),
            )
            button.grid(row=0, column=index, padx=(0, 10) if index < len(buttons) - 1 else 0)

    def _dialog_geometry(self, master) -> str:
        width = 480
        height = 230
        if master is None:
            return f"{width}x{height}"
        master.update_idletasks()
        x = master.winfo_rootx() + max(20, (master.winfo_width() - width) // 2)
        y = master.winfo_rooty() + max(20, (master.winfo_height() - height) // 2)
        return f"{width}x{height}+{x}+{y}"

    def _close(self, result: bool) -> None:
        self.result = result
        self.grab_release()
        self.destroy()

    def show(self) -> bool:
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window()
        return self.result


class WhisperModelChoiceDialog(ctk.CTkToplevel):
    def __init__(self, master, *, default_model: str = DEFAULT_WHISPERX_MODEL, prepared_model: str | None = None) -> None:
        super().__init__(master)
        self.result: str | None = None
        self._selected_model = ctk.StringVar(value=prepared_model or default_model)
        self.title("Choose WhisperX model")
        self.transient(master)
        self.resizable(False, True)
        self.configure(fg_color="#0f141b")
        self.geometry(self._dialog_geometry(master))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        shell = ctk.CTkFrame(self, corner_radius=20, fg_color=CARD_COLOR, border_width=1, border_color="#263244")
        shell.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(4, weight=1)

        banner = ctk.CTkFrame(shell, corner_radius=14, fg_color=WARNING_COLOR, height=8)
        banner.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 0))
        ctk.CTkLabel(shell, text="Choose WhisperX model size", font=ui_font(18, weight="bold")).grid(
            row=1, column=0, sticky="w", padx=18, pady=(16, 6)
        )
        ctk.CTkLabel(
            shell,
            text=(
                "Pick the WhisperX model to download now. Smaller models install faster and use less RAM or VRAM. "
                "Larger models can improve accuracy but take longer to download and run."
            ),
            justify="left",
            anchor="w",
            wraplength=540,
            text_color=TEXT_MUTED,
            font=ui_font(12),
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))

        if prepared_model and prepared_model in WHISPERX_MODEL_PRESETS:
            prepared_preset = WHISPERX_MODEL_PRESETS[prepared_model]
            helper_text = (
                f"Current active model: {prepared_preset.display_name} ({prepared_model}, {prepared_preset.size_hint}). "
                "Installing another model will switch future transcription jobs to the newly downloaded size."
            )
        else:
            default_preset = WHISPERX_MODEL_PRESETS[default_model]
            helper_text = (
                f"Recommended starter choice: {default_preset.display_name} ({default_model}, {default_preset.size_hint})."
            )
        ctk.CTkLabel(
            shell,
            text=helper_text,
            justify="left",
            anchor="w",
            wraplength=540,
            text_color="#d0d8e2",
            font=ui_font(11),
        ).grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 12))

        options_frame = ctk.CTkScrollableFrame(
            shell,
            fg_color="transparent",
            height=340,
            corner_radius=0,
        )
        options_frame.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 12))
        options_frame.grid_columnconfigure(0, weight=1)
        for index, model_name in enumerate(SUPPORTED_WHISPERX_MODELS):
            preset = WHISPERX_MODEL_PRESETS[model_name]
            row = ctk.CTkFrame(options_frame, corner_radius=12, fg_color="#182230", border_width=1, border_color="#263244")
            row.grid(row=index, column=0, sticky="ew", pady=(0, 8))
            row.grid_columnconfigure(0, weight=1)
            radio = ctk.CTkRadioButton(
                row,
                text=f"{preset.display_name}  |  {model_name}",
                variable=self._selected_model,
                value=model_name,
                font=ui_font(13, weight="bold"),
            )
            radio.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                row,
                text=f"{preset.size_hint} - {preset.description}",
                text_color=TEXT_MUTED,
                justify="left",
                anchor="w",
                wraplength=500,
                font=ui_font(11),
            ).grid(row=1, column=0, sticky="w", padx=38, pady=(0, 10))

        button_row = ctk.CTkFrame(shell, fg_color="transparent")
        button_row.grid(row=5, column=0, sticky="e", padx=18, pady=(0, 18))
        ctk.CTkButton(
            button_row,
            text="Cancel",
            width=120,
            fg_color="#233040",
            hover_color="#314359",
            font=ui_font(12),
            command=self._cancel,
        ).grid(row=0, column=0, padx=(0, 10))
        ctk.CTkButton(
            button_row,
            text="Download selected model",
            width=190,
            fg_color=WARNING_COLOR,
            hover_color="#f08c00",
            font=ui_font(12),
            command=self._confirm,
        ).grid(row=0, column=1)

    def _dialog_geometry(self, master) -> str:
        width = 640
        height = 720
        if master is None:
            return f"{width}x{height}"
        master.update_idletasks()
        x = master.winfo_rootx() + max(20, (master.winfo_width() - width) // 2)
        y = master.winfo_rooty() + max(20, (master.winfo_height() - height) // 2)
        return f"{width}x{height}+{x}+{y}"

    def _cancel(self) -> None:
        self.result = None
        self.grab_release()
        self.destroy()

    def _confirm(self) -> None:
        self.result = self._selected_model.get()
        self.grab_release()
        self.destroy()

    def show(self) -> str | None:
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window()
        return self.result


def choose_video_file(master=None) -> Path | None:
    filename = filedialog.askopenfilename(
        parent=master,
        title="Select a source video",
        filetypes=[("Video files", " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS)))],
    )
    return Path(filename) if filename else None


def choose_video_files(master=None) -> list[Path]:
    filenames = filedialog.askopenfilenames(
        parent=master,
        title="Add videos to the queue",
        filetypes=[("Video files", " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS)))],
    )
    return [Path(filename) for filename in filenames if filename]


def choose_executable(master, title: str) -> Path | None:
    filename = filedialog.askopenfilename(
        parent=master,
        title=title,
        filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
    )
    return Path(filename) if filename else None


def show_error(master, title: str, message: str) -> None:
    ModalMessageDialog(
        master,
        title_text=title,
        message=message,
        accent_color=ERROR_COLOR,
        buttons=[("Close", True)],
    ).show()


def show_info(master, title: str, message: str) -> None:
    ModalMessageDialog(
        master,
        title_text=title,
        message=message,
        accent_color=SUCCESS_COLOR,
        buttons=[("Close", True)],
    ).show()


def confirm(master, title: str, message: str) -> bool:
    return ModalMessageDialog(
        master,
        title_text=title,
        message=message,
        accent_color=WARNING_COLOR,
        buttons=[("Cancel", False), ("Confirm", True)],
    ).show()


def choose_whisperx_model(
    master=None,
    *,
    default_model: str = DEFAULT_WHISPERX_MODEL,
    prepared_model: str | None = None,
) -> str | None:
    return WhisperModelChoiceDialog(
        master,
        default_model=default_model,
        prepared_model=prepared_model,
    ).show()


def open_folder(path: Path) -> None:
    open_in_explorer(path)
