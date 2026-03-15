from __future__ import annotations

import re


_PER_TITLE_PREFIX_RE = re.compile(
    r"""
    ^.*?
    (?:
        Herr|Herrn|Frau
    )
    \s+
    """,
    re.IGNORECASE | re.VERBOSE,
)


def cleanup_outer_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


def cleanup_trailing_punctuation(text: str, start: int, end: int) -> tuple[int, int]:
    trailing_chars = " \t\r\n,.;:!?)]}\"'`#-_/\\|~+="

    while end > start and text[end - 1] in trailing_chars:
        end -= 1

    return start, end


def cut_left_to_person_name(span: str) -> tuple[int, str]:
    match = _PER_TITLE_PREFIX_RE.match(span)

    if match is None:
        return 0, span

    offset = match.end()
    return offset, span[offset:]