from __future__ import annotations

from core.typen import Treffer

from .normalize_org_span import cleanup_outer_whitespace
from .normalize_org_span import cleanup_trailing_punctuation
from .extend_org_suffix import extend_span_to_right_suffix
from .cut_org_suffix import cut_span_at_suffix
from .validate_org_span import is_valid_org_span


def process_org_hit(text: str, hit: Treffer) -> Treffer | None:
    # Entfernt führende und trailing Whitespaces aus dem ursprünglichen Span
    start, end = cleanup_outer_whitespace(text, hit.start, hit.ende)

    # Leere Spans verwerfen
    if start >= end:
        return None

    # Versucht ein recht daneben stehendes Organisationssuffix einzubeziehen
    # Beispiel: "Franke Bau" → "Franke Bau GmbH"
    start, end = extend_span_to_right_suffix(text, start, end)

    # Schneidet den Span auf das letzte erkannte Organisationssuffix zu
    start, end = cut_span_at_suffix(text, start, end)

    # Entfernt abschließende Satzzeichen oder Formatierungsreste
    start, end = cleanup_trailing_punctuation(text, start, end)

    # Entfernt erneut mögliche Whitespaces nach vorherigen Anpassungen
    start, end = cleanup_outer_whitespace(text, start, end)

    # Leere Spans verwerfen
    if start >= end:
        return None

    span = text[start:end]

    # Validiert, ob der Span eine plausible Organisation darstellt
    if not is_valid_org_span(span):
        return None

    # Gültigen Organisations-Treffer zurückgeben
    return Treffer(
        start,
        end,
        "ORG",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )