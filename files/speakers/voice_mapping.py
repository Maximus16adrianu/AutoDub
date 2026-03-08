"""Map speaker labels to Piper voices."""

from __future__ import annotations

import random

from files.tts.voice_registry import get_voice


def assign_voices_to_speakers(
    speaker_labels: list[str],
    available_voice_ids: list[str],
    max_voices: int,
    random_seed: str = "",
    speaker_gender_hints: dict[str, str] | None = None,
) -> dict[str, str]:
    if not speaker_labels or not available_voice_ids:
        return {}
    unique_candidates = list(dict.fromkeys(available_voice_ids))
    voice_pool = unique_candidates[: max(1, min(max_voices, len(unique_candidates)))]
    rng = random.Random(random_seed)
    mapping: dict[str, str] = {}
    unique_speakers = sorted(set(speaker_labels))
    unused_voices = list(voice_pool)
    for speaker in unique_speakers:
        speaker_gender = (speaker_gender_hints or {}).get(speaker, "unknown")
        preferred_unused = _matching_voice_ids(unused_voices, speaker_gender)
        if preferred_unused:
            chosen_voice = preferred_unused[0]
            unused_voices.remove(chosen_voice)
            mapping[speaker] = chosen_voice
        elif unused_voices:
            chosen_voice = unused_voices[0]
            unused_voices.remove(chosen_voice)
            mapping[speaker] = chosen_voice
        else:
            preferred_pool = _matching_voice_ids(voice_pool, speaker_gender)
            mapping[speaker] = rng.choice(preferred_pool or voice_pool)
    return mapping


def _matching_voice_ids(voice_ids: list[str], speaker_gender: str) -> list[str]:
    if not voice_ids:
        return []
    if speaker_gender == "female":
        exact = [voice_id for voice_id in voice_ids if get_voice(voice_id).gender_hint == "female"]
        neutral = [voice_id for voice_id in voice_ids if get_voice(voice_id).gender_hint == "neutral"]
        return exact or neutral
    if speaker_gender == "male":
        exact = [voice_id for voice_id in voice_ids if get_voice(voice_id).gender_hint == "male"]
        neutral = [voice_id for voice_id in voice_ids if get_voice(voice_id).gender_hint == "neutral"]
        return exact or neutral
    return list(voice_ids)
