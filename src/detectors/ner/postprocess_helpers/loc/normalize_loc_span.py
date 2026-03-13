from __future__ import annotations

import re

from core.typen import Treffer
from ..shared.normalize_text import normalize_whitespace


_PLZ_AM_ANFANG_RE = re.compile(
    r"""
    ^
    (?:
        D[-\s]?
    )?
    (?P<plz>\d{5})
    (?P<sep>\s+)
    """,
    re.VERBOSE,
)


def _strip_leading_plz_from_loc_segment(segment: str) -> tuple[int, str]:
    match = _PLZ_AM_ANFANG_RE.match(segment)
    if not match:
        return 0, segment.strip()

    offset = match.end()
    cleaned = segment[offset:].strip()
    return offset, cleaned


def normalize_loc_span(text: str, hit: Treffer) -> Treffer | None:
    raw_span = text[hit.start:hit.ende]

    if not raw_span.strip():
        return None

    lines = raw_span.splitlines()
    if not lines:
        return None

    first_line_original = lines[0]
    first_line = normalize_whitespace(first_line_original)

    if not first_line:
        return None

    line_offset = raw_span.find(first_line_original)
    base_abs_start = hit.start + line_offset
    base_abs_end = base_abs_start + len(first_line_original.rstrip())

    while base_abs_start < base_abs_end and text[base_abs_start].isspace():
        base_abs_start += 1
    while base_abs_end > base_abs_start and text[base_abs_end - 1].isspace():
        base_abs_end -= 1

    if base_abs_start >= base_abs_end:
        return None

    candidate_raw = text[base_abs_start:base_abs_end]
    plz_offset, candidate_clean = _strip_leading_plz_from_loc_segment(candidate_raw)

    if not candidate_clean:
        return None

    abs_start = base_abs_start + plz_offset
    abs_end = abs_start + len(candidate_clean)

    if abs_start >= abs_end:
        return None

    return Treffer(
        abs_start,
        abs_end,
        "LOC",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )