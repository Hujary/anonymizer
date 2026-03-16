from __future__ import annotations

import re


_PER_LEFT_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:
        Guten\s+Tag
        |Hallo
        |Hi
        |Hey
        |Moin
        |Servus
        |Liebe
        |Lieber
        |Herr
        |Herrn
        |Frau
    )
    \s+
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PER_RIGHT_SPLIT_RE = re.compile(
    r"""
    (?:
        \r\n
        |\n
        |\r
        |[,:;]\s
        |\s[-–—]\s
        |\s\(\s*
    )
    """,
    re.VERBOSE,
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


def cut_left_person_prefix(span: str) -> tuple[int, str]:
    current = span
    total_offset = 0

    while True:
        match = _PER_LEFT_PREFIX_RE.match(current)

        if match is None:
            break

        offset = match.end()
        total_offset += offset
        current = current[offset:]

    return total_offset, current


def cut_right_person_suffix(span: str) -> tuple[int, str]:
    current = span

    match = _PER_RIGHT_SPLIT_RE.search(current)
    if match is None:
        return len(current), current

    cut_end = match.start()
    current = current[:cut_end]
    return cut_end, current