from __future__ import annotations

import re

from .org_blacklists import ORG_LEGAL_SUFFIXES


_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)

_ORG_SUFFIX_NEAR_RIGHT_RE = re.compile(
    rf"""
    ^
    (?P<gap>[\s\.,;:()$begin:math:display$$end:math:display${{}}"'`-]{{0,3}})
    (?P<suffix>{_SUFFIX_TOKEN_PATTERN})
    (?=$|[\s\.,;:!?\)\]\}}"'`])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extend_span_to_right_suffix(text: str, start: int, end: int) -> tuple[int, int]:
    tail = text[end:end + 16]

    match = _ORG_SUFFIX_NEAR_RIGHT_RE.match(tail)

    if match is None:
        return start, end

    suffix_end = end + match.end("suffix")

    return start, suffix_end