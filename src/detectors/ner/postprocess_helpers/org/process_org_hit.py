from __future__ import annotations

from core.typen import Treffer

from .normalize_org_span import cleanup_outer_whitespace
from .normalize_org_span import cleanup_trailing_punctuation
from .extend_org_suffix import extend_span_to_right_suffix
from .cut_org_suffix import cut_span_at_suffix
from .validate_org_span import is_valid_org_span


def process_org_hit(text: str, hit: Treffer) -> Treffer | None:
    start, end = cleanup_outer_whitespace(text, hit.start, hit.ende)

    if start >= end:
        return None

    start, end = extend_span_to_right_suffix(text, start, end)
    start, end = cut_span_at_suffix(text, start, end)
    start, end = cleanup_trailing_punctuation(text, start, end)
    start, end = cleanup_outer_whitespace(text, start, end)

    if start >= end:
        return None

    span = text[start:end]

    if not is_valid_org_span(span):
        return None

    return Treffer(
        start,
        end,
        "ORG",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )