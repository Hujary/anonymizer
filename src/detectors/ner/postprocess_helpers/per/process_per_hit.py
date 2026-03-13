from __future__ import annotations

from core.typen import Treffer

from .normalize_per_span import cleanup_outer_whitespace
from .normalize_per_span import cleanup_trailing_punctuation
from .validate_person_span import is_valid_person_span


def process_per_hit(text: str, hit: Treffer) -> Treffer | None:
    # Entfernt führende und trailing Whitespaces aus dem ursprünglichen Span
    start, end = cleanup_outer_whitespace(text, hit.start, hit.ende)

    # Entfernt abschließende Satzzeichen (z.B. Punkt, Komma, Klammern)
    start, end = cleanup_trailing_punctuation(text, start, end)

    # Entfernt erneut mögliche Whitespaces nach der Bereinigung
    start, end = cleanup_outer_whitespace(text, start, end)

    # Leere Spans verwerfen
    if start >= end:
        return None

    span = text[start:end]

    # Prüft, ob der Span eine plausible Person darstellt
    if not is_valid_person_span(span):
        return None

    # Gültigen Person-Treffer zurückgeben
    return Treffer(
        start,
        end,
        "PER",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )