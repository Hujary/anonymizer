from __future__ import annotations


def cleanup_outer_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


def cleanup_trailing_punctuation(text: str, start: int, end: int) -> tuple[int, int]:
    trailing_chars = " \t\r\n,.;:!?)]}\"'`"

    while end > start and text[end - 1] in trailing_chars:
        end -= 1

    return start, end