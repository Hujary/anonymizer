from __future__ import annotations

import re

from .org_blacklists import ORG_LEGAL_SUFFIXES


_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)


_ALLOWED_INTERMEDIATE_RE = re.compile(
    r"^[A-Za-zÄÖÜäöüß0-9&\-\/\.\(\) ]*$"
)


_SUFFIX_SEARCH_RE = re.compile(
    rf"""
    (?<![A-Za-zÄÖÜäöüß])
    (?P<suffix>{_SUFFIX_TOKEN_PATTERN})
    (?=$|[^A-Za-zÄÖÜäöüß])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extend_span_to_right_suffix(text: str, start: int, end: int) -> tuple[int, int]:
    if start < 0 or end <= start or end > len(text):
        return start, end

    tail = text[end:end + 80]

    if not tail:
        return start, end

    suffix_match = _SUFFIX_SEARCH_RE.search(tail)
    if suffix_match is None:
        return start, end

    intermediate = tail[:suffix_match.start("suffix")]

    if "\n" in intermediate or "\r" in intermediate:
        return start, end

    if any(ch in intermediate for ch in ":;!?"):
        return start, end

    if not _ALLOWED_INTERMEDIATE_RE.match(intermediate):
        return start, end

    candidate_extension = intermediate + suffix_match.group("suffix")
    token_count = len(re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", candidate_extension))
    if token_count > 8:
        return start, end

    new_end = end + suffix_match.end("suffix")
    return start, new_end