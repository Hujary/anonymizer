from __future__ import annotations

from core.typen import Treffer

from .extract_street_span import extract_street_span_from_loc
from .normalize_loc_span import normalize_loc_span
from .validate_loc_span import is_plausible_loc_span
from .loc_blacklists import TECHNICAL_LOC_BLACKLIST


def process_loc_hit(text: str, hit: Treffer) -> Treffer | None:
    street_span = extract_street_span_from_loc(text, hit.start, hit.ende)

    if street_span is not None:
        start, end = street_span

        return Treffer(
            start,
            end,
            "LOC",
            hit.source,
            from_regex=hit.from_regex,
            from_ner=hit.from_ner,
        )

    normalized_loc = normalize_loc_span(text, hit)

    if normalized_loc is None:
        return None

    span = text[normalized_loc.start:normalized_loc.ende].strip()

    if not span:
        return None

    tokens = span.lower().split()

    for token in tokens:
        if token in TECHNICAL_LOC_BLACKLIST:
            return None

    if not is_plausible_loc_span(span):
        return None

    return normalized_loc