"""WhisperX response conversion helpers."""

from __future__ import annotations

from files.stt.alignment import normalize_word_timestamps
from files.stt.schemas import TranscriptResult, TranscriptSegment, WordToken


def build_transcript_result(raw_segments: list[dict], source_language: str, duration: float | None = None) -> TranscriptResult:
    segments: list[TranscriptSegment] = []
    words: list[WordToken] = []
    for segment_index, raw_segment in enumerate(raw_segments):
        segment_id = f"seg-{segment_index:04d}"
        text = (raw_segment.get("text") or "").strip()
        segment = TranscriptSegment(
            id=segment_id,
            start=float(raw_segment.get("start", 0.0)),
            end=float(raw_segment.get("end", 0.0)),
            text=text,
            language=source_language,
        )
        raw_words = raw_segment.get("words") or []
        for word_index, raw_word in enumerate(raw_words):
            word_id = f"{segment_id}-w{word_index:03d}"
            word = WordToken(
                id=word_id,
                text=(raw_word.get("word") or raw_word.get("text") or "").strip(),
                start=float(raw_word.get("start", segment.start)),
                end=float(raw_word.get("end", segment.end)),
                confidence=float(raw_word["score"]) if raw_word.get("score") is not None else None,
                segment_id=segment_id,
            )
            words.append(word)
            segment.word_ids.append(word_id)
        if not segment.word_ids and text:
            fallback_word_id = f"{segment_id}-w000"
            words.append(
                WordToken(
                    id=fallback_word_id,
                    text=text,
                    start=segment.start,
                    end=segment.end,
                    segment_id=segment_id,
                )
            )
            segment.word_ids.append(fallback_word_id)
        segments.append(segment)
    normalize_word_timestamps(words)
    return TranscriptResult(
        source_language=source_language,
        segments=segments,
        words=words,
        duration=duration,
    )
