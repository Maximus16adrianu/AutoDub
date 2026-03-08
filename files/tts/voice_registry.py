"""Managed Piper voice registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PiperVoice:
    voice_id: str
    language_code: str
    display_name: str
    model_url: str
    config_url: str
    gender_hint: str = "neutral"
    sample_rate: int = 22_050


PIPER_RUNTIME_ZIP_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
PIPER_VOICE_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"


def _build_voice(voice_id: str, language_code: str, display_name: str, gender_hint: str = "neutral") -> PiperVoice:
    locale, name, quality = voice_id.split("-", 2)
    relative = f"{language_code}/{locale}/{name}/{quality}/{voice_id}"
    return PiperVoice(
        voice_id=voice_id,
        language_code=language_code,
        display_name=display_name,
        model_url=f"{PIPER_VOICE_BASE_URL}/{relative}.onnx?download=true",
        config_url=f"{PIPER_VOICE_BASE_URL}/{relative}.onnx.json?download=true",
        gender_hint=gender_hint,
    )


VOICE_REGISTRY = {
    "en_US-amy-medium": _build_voice("en_US-amy-medium", "en", "Amy Medium", "female"),
    "en_US-joe-medium": _build_voice("en_US-joe-medium", "en", "Joe Medium", "male"),
    "en_US-john-medium": _build_voice("en_US-john-medium", "en", "John Medium", "male"),
    "en_US-bryce-medium": _build_voice("en_US-bryce-medium", "en", "Bryce Medium", "male"),
    "en_US-danny-low": _build_voice("en_US-danny-low", "en", "Danny Low", "male"),
    "en_GB-alan-medium": _build_voice("en_GB-alan-medium", "en", "Alan Medium", "male"),
    "en_GB-alba-medium": _build_voice("en_GB-alba-medium", "en", "Alba Medium", "female"),
    "de_DE-thorsten-medium": _build_voice("de_DE-thorsten-medium", "de", "Thorsten Medium", "male"),
    "de_DE-kerstin-low": _build_voice("de_DE-kerstin-low", "de", "Kerstin Low", "female"),
    "de_DE-ramona-low": _build_voice("de_DE-ramona-low", "de", "Ramona Low", "female"),
    "de_DE-pavoque-low": _build_voice("de_DE-pavoque-low", "de", "Pavoque Low", "neutral"),
    "de_DE-eva_k-x_low": _build_voice("de_DE-eva_k-x_low", "de", "Eva K X-Low", "female"),
    "de_DE-karlsson-low": _build_voice("de_DE-karlsson-low", "de", "Karlsson Low", "male"),
    "es_ES-davefx-medium": _build_voice("es_ES-davefx-medium", "es", "DaveFX Medium", "male"),
    "es_MX-ald-medium": _build_voice("es_MX-ald-medium", "es", "Ald Medium", "male"),
    "es_MX-claude-high": _build_voice("es_MX-claude-high", "es", "Claude High", "male"),
    "es_AR-daniela-high": _build_voice("es_AR-daniela-high", "es", "Daniela High", "female"),
    "es_ES-carlfm-x_low": _build_voice("es_ES-carlfm-x_low", "es", "CarlFM X-Low", "male"),
    "fr_FR-tom-medium": _build_voice("fr_FR-tom-medium", "fr", "Tom Medium", "male"),
    "fr_FR-siwis-medium": _build_voice("fr_FR-siwis-medium", "fr", "Siwis Medium", "female"),
    "fr_FR-gilles-low": _build_voice("fr_FR-gilles-low", "fr", "Gilles Low", "male"),
    "fr_FR-mls_1840-low": _build_voice("fr_FR-mls_1840-low", "fr", "MLS 1840 Low", "neutral"),
    "it_IT-paola-medium": _build_voice("it_IT-paola-medium", "it", "Paola Medium", "female"),
    "it_IT-riccardo-x_low": _build_voice("it_IT-riccardo-x_low", "it", "Riccardo X-Low", "male"),
    "pt_BR-faber-medium": _build_voice("pt_BR-faber-medium", "pt", "Faber Medium", "male"),
    "pt_BR-cadu-medium": _build_voice("pt_BR-cadu-medium", "pt", "Cadu Medium", "male"),
    "pt_BR-jeff-medium": _build_voice("pt_BR-jeff-medium", "pt", "Jeff Medium", "male"),
    "pt_BR-edresson-low": _build_voice("pt_BR-edresson-low", "pt", "Edresson Low", "male"),
    "nl_NL-ronnie-medium": _build_voice("nl_NL-ronnie-medium", "nl", "Ronnie Medium", "male"),
    "nl_NL-pim-medium": _build_voice("nl_NL-pim-medium", "nl", "Pim Medium", "male"),
    "nl_BE-nathalie-medium": _build_voice("nl_BE-nathalie-medium", "nl", "Nathalie Medium", "female"),
    "nl_BE-rdh-medium": _build_voice("nl_BE-rdh-medium", "nl", "RDH Medium", "neutral"),
    "nl_NL-mls_5809-low": _build_voice("nl_NL-mls_5809-low", "nl", "MLS 5809 Low", "neutral"),
    "ru_RU-denis-medium": _build_voice("ru_RU-denis-medium", "ru", "Denis Medium", "male"),
    "ru_RU-dmitri-medium": _build_voice("ru_RU-dmitri-medium", "ru", "Dmitri Medium", "male"),
    "ru_RU-irina-medium": _build_voice("ru_RU-irina-medium", "ru", "Irina Medium", "female"),
    "ru_RU-ruslan-medium": _build_voice("ru_RU-ruslan-medium", "ru", "Ruslan Medium", "male"),
    "zh_CN-huayan-medium": _build_voice("zh_CN-huayan-medium", "zh", "Huayan Medium", "female"),
    "zh_CN-huayan-x_low": _build_voice("zh_CN-huayan-x_low", "zh", "Huayan X-Low", "female"),
}


def get_voice(voice_id: str) -> PiperVoice:
    return VOICE_REGISTRY[voice_id]


def all_voices() -> list[PiperVoice]:
    return list(VOICE_REGISTRY.values())


def voices_for_language(language_code: str) -> list[PiperVoice]:
    return [voice for voice in VOICE_REGISTRY.values() if voice.language_code == language_code]


def voice_ids_for_language(language_code: str, *, balance_gender: bool = False) -> list[str]:
    language_voices = voices_for_language(language_code)
    if not balance_gender:
        return [voice.voice_id for voice in language_voices]
    buckets = {
        "female": [voice for voice in language_voices if voice.gender_hint == "female"],
        "male": [voice for voice in language_voices if voice.gender_hint == "male"],
        "neutral": [voice for voice in language_voices if voice.gender_hint not in {"female", "male"}],
    }
    ordered: list[str] = []
    while any(buckets.values()):
        for gender in ("female", "male", "neutral"):
            if buckets[gender]:
                ordered.append(buckets[gender].pop(0).voice_id)
    return ordered
