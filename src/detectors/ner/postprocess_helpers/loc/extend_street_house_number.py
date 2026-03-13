from __future__ import annotations

import re


_HAUSNUMMER_DIREKT_RE = re.compile(
    r"""
    ^
    (?P<ws>\s+)
    (?P<hausnummer>
        \d{1,4}[A-Za-z]?
        (?:\s*[-/]\s*\d{1,4}[A-Za-z]?)?
    )
    """,
    re.VERBOSE,
)


def find_direct_house_number(text: str, end_pos: int) -> tuple[int, int] | None:
    tail = text[end_pos:]
    match = _HAUSNUMMER_DIREKT_RE.match(tail)

    if not match:
        return None

    whitespace = match.group("ws")
    hausnummer = match.group("hausnummer")

    if not hausnummer:
        return None

    start = end_pos + len(whitespace)
    end = start + len(hausnummer)
    return start, end