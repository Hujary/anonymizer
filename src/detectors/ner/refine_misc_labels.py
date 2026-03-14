from __future__ import annotations

import re
from typing import List

from core.typen import Treffer

from .postprocess_helpers.org.validate_org_span import is_valid_org_span
from .postprocess_helpers.org.org_blacklists import ORG_LEGAL_SUFFIXES


_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)

_ORG_SUFFIX_CHAIN_RE = re.compile(
    rf"""
    (?P<suffix_chain>
        {_SUFFIX_TOKEN_PATTERN}
        (
            \s*&\s*Co\.?\s*
            {_SUFFIX_TOKEN_PATTERN}
        )?
    )
    (?=$|[^A-Za-zÄÖÜäöüß])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _strip_outer_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


def _find_last_org_suffix_end(span: str) -> int | None:
    matches = list(_ORG_SUFFIX_CHAIN_RE.finditer(span))

    if not matches:
        return None

    return matches[-1].end("suffix_chain")


def _looks_like_org_misc(text: str, start: int, end: int) -> tuple[bool, int, int]:
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        return False, start, end

    raw_span = text[start:end]

    suffix_end_in_span = _find_last_org_suffix_end(raw_span)
    if suffix_end_in_span is None:
        return False, start, end

    candidate_raw = raw_span[:suffix_end_in_span]

    # Kein Zeilenumbruch vor oder innerhalb des eigentlichen ORG-Kandidaten
    if "\n" in candidate_raw or "\r" in candidate_raw:
        return False, start, end

    new_end = start + suffix_end_in_span
    new_start, new_end = _strip_outer_whitespace(text, start, new_end)

    if new_start >= new_end:
        return False, new_start, new_end

    candidate = text[new_start:new_end]

    if not is_valid_org_span(candidate):
        return False, new_start, new_end

    return True, new_start, new_end


def refine_misc_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()

        if label != "MISC":
            out.append(h)
            continue

        is_org, new_start, new_end = _looks_like_org_misc(text, h.start, h.ende)

        if is_org:
            out.append(
                Treffer(
                    new_start,
                    new_end,
                    "ORG",
                    h.source,
                    from_regex=h.from_regex,
                    from_ner=h.from_ner,
                )
            )

    return out