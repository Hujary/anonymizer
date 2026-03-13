from __future__ import annotations

import re

from .org_blacklists import ORG_LEGAL_SUFFIXES


_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)

_ORG_SUFFIX_IN_SPAN_RE = re.compile(
    rf"""
    (?P<suffix>{_SUFFIX_TOKEN_PATTERN})
    (?=$|[\s\.,;:!?\)\]\}}"'`])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def cut_span_at_suffix(text: str, start: int, end: int) -> tuple[int, int]:
    span = text[start:end]

    matches = list(_ORG_SUFFIX_IN_SPAN_RE.finditer(span))

    if not matches:
        return start, end

    last = matches[-1]

    cut_end = start + last.end("suffix")

    return start, cut_end