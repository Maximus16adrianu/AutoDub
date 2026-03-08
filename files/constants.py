"""Shared application constants."""

from __future__ import annotations

from dataclasses import dataclass


APP_NAME = "AutoDub Studio"
APP_DESCRIPTION = "Offline-first automatic video dubbing for Windows."
PYTHON_MIN_VERSION = (3, 10)
DEFAULT_WHISPERX_MODEL = "small"
DEFAULT_DEVICE = "auto"
DEFAULT_SOURCE_LANGUAGE = "auto"
DEFAULT_TARGET_LANGUAGE = "en"
DEFAULT_VOICE_MODE = "single"
DEFAULT_MAX_SPEAKER_VOICES = 3
DEFAULT_AUTO_MATCH_SPEAKER_GENDER = False
DEFAULT_SUBTITLES_ENABLED = True
DEFAULT_SUBTITLE_LANGUAGE = "target"
DEFAULT_RETIME_VIDEO_TO_DUB = True
DEFAULT_APPEARANCE_MODE = "dark"
SETTINGS_FILENAME = "settings.json"

DATA_DIR_NAMES = (
    "cache",
    "logs",
    "models",
    "projects",
    "exports",
    "settings",
    "temp",
)

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".wmv",
    ".m4v",
    ".webm",
}

CRITICAL_PYTHON_PACKAGES = {
    "customtkinter": "customtkinter",
    "PIL": "Pillow",
    "requests": "requests",
    "torch": "torch",
    "transformers": "transformers",
    "soundfile": "soundfile",
    "whisperx": "whisperx",
    "argostranslate": "argostranslate",
    "speechbrain": "speechbrain",
    "sklearn": "scikit-learn",
    "numpy": "numpy",
    "audonnx": "audonnx",
    "onnxruntime": "onnxruntime",
}

PIPELINE_STAGES = (
    "preparing project",
    "probing video",
    "extracting audio",
    "transcribing audio",
    "aligning words",
    "building segments",
    "grouping speakers",
    "translating segments",
    "generating speech",
    "fitting durations",
    "muxing final audio/video",
    "writing exports",
)

LANGUAGE_LABELS = {
    "auto": "Auto detect",
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}

SUPPORTED_DUB_LANGUAGE_CODES = (
    "en",
    "de",
    "es",
    "fr",
    "it",
    "pt",
    "nl",
    "ru",
    "zh",
)

SUBTITLE_LANGUAGE_LABELS = {
    "target": "Match dub language",
    "source": "Match source language",
}

SPEAKER_LABEL_TEMPLATE = "SPEAKER_{index:02d}"


@dataclass(frozen=True)
class WhisperXModelPreset:
    model_name: str
    display_name: str
    repo_id: str
    size_hint: str
    description: str


WHISPERX_MODEL_PRESETS = {
    "tiny": WhisperXModelPreset(
        "tiny",
        "Tiny",
        "Systran/faster-whisper-tiny",
        "~150 MB",
        "Fastest download and lowest resource use.",
    ),
    "base": WhisperXModelPreset(
        "base",
        "Base",
        "Systran/faster-whisper-base",
        "~300 MB",
        "Lightweight balance for quick offline jobs.",
    ),
    "small": WhisperXModelPreset(
        "small",
        "Small",
        "Systran/faster-whisper-small",
        "~1 GB",
        "Recommended default for general desktop use.",
    ),
    "medium": WhisperXModelPreset(
        "medium",
        "Medium",
        "Systran/faster-whisper-medium",
        "~3 GB",
        "Higher accuracy with noticeably heavier compute.",
    ),
    "large-v2": WhisperXModelPreset(
        "large-v2",
        "Large V2",
        "Systran/faster-whisper-large-v2",
        "~6 GB",
        "Largest offline option here, best for difficult audio.",
    ),
}
SUPPORTED_WHISPERX_MODELS = tuple(WHISPERX_MODEL_PRESETS.keys())


@dataclass(frozen=True)
class PiperVoicePreset:
    language_code: str
    voice_id: str
    display_name: str


DEFAULT_PIPER_VOICE_BY_LANGUAGE = {
    "en": PiperVoicePreset("en", "en_US-amy-medium", "Amy Medium"),
    "de": PiperVoicePreset("de", "de_DE-thorsten-medium", "Thorsten Medium"),
    "es": PiperVoicePreset("es", "es_ES-davefx-medium", "DaveFX Medium"),
    "fr": PiperVoicePreset("fr", "fr_FR-tom-medium", "Tom Medium"),
    "it": PiperVoicePreset("it", "it_IT-paola-medium", "Paola Medium"),
    "pt": PiperVoicePreset("pt", "pt_BR-faber-medium", "Faber Medium"),
    "nl": PiperVoicePreset("nl", "nl_NL-ronnie-medium", "Ronnie Medium"),
    "ru": PiperVoicePreset("ru", "ru_RU-denis-medium", "Denis Medium"),
    "zh": PiperVoicePreset("zh", "zh_CN-huayan-medium", "Huayan Medium"),
}
