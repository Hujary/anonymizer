from __future__ import annotations

from core.typen import Treffer

from .normalize_per_span import cleanup_outer_whitespace
from .normalize_per_span import cleanup_trailing_punctuation
from .validate_person_span import is_valid_person_span


def process_per_hit(text: str, hit: Treffer) -> Treffer | None:
    # Führende und nachgestellte Whitespaces entfernen
    start, end = cleanup_outer_whitespace(text, hit.start, hit.ende)

    # Rechte Restzeichen wie Punkt, Doppelpunkt, #-Artefakte usw. abschneiden
    start, end = cleanup_trailing_punctuation(text, start, end)

    # Nach dem Kürzen erneut Whitespaces entfernen
    start, end = cleanup_outer_whitespace(text, start, end)

    # Leere Spans direkt verwerfen
    if start >= end:
        return None

    span = text[start:end]

    # Nur plausible Personenspans akzeptieren
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