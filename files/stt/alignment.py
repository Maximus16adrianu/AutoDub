"""Alignment cleanup helpers."""

from __future__ import annotations

from files.stt.schemas import WordToken


def normalize_word_timestamps(words: list[WordToken]) -> list[WordToken]:
    previous_end = 0.0
    for word in words:
        if word.start < previous_end:
            word.start = previous_end
        if word.end < word.start:
            word.end = word.start
        previous_end = word.end
    return words
