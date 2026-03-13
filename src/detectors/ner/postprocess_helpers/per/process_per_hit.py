from __future__ import annotations

from core.typen import Treffer

from .normalize_per_span import cleanup_outer_whitespace
from .normalize_per_span import cleanup_trailing_punctuation
from .validate_person_span import is_valid_person_span


def process_per_hit(text: str, hit: Treffer) -> Treffer | None:
    start, end = cleanup_outer_whitespace(text, hit.start, hit.ende)

    start, end = cleanup_trailing_punctuation(text, start, end)

    start, end = cleanup_outer_whitespace(text, start, end)

    if start >= end:
        return None

    span = text[start:end]

    if not is_valid_person_span(span):
        return None

    return Treffer(
        start,
        end,
        "PER",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )