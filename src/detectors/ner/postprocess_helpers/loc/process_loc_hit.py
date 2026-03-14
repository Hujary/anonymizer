from __future__ import annotations

import re

from core.typen import Treffer

from .extract_street_span import extract_street_span_from_loc
from .normalize_loc_span import normalize_loc_span
from .validate_loc_span import is_plausible_loc_span
from .loc_blacklists import TECHNICAL_LOC_BLACKLIST
from .loc_id_validator import is_invalid_loc_id


# Token-Splitting für LOC-Spans (z.B. "Monitoring-Service")
_LOC_TOKEN_SPLIT_RE = re.compile(r"[\s\-_\/]+")


def _normalize_blacklist_token(token: str) -> str:
    # Normalisiert Tokens für Vergleich mit Blacklists
    strip_chars = ",.;:(){}[]\"'`„“‚‘-–—"
    return token.strip().lower().strip(strip_chars)


def _contains_technical_loc_term(span: str) -> bool:
    # Prüft, ob der Span technische Begriffe enthält, die keine echten Orte sind
    raw_parts = _LOC_TOKEN_SPLIT_RE.split(span)

    for raw in raw_parts:
        token = _normalize_blacklist_token(raw)

        if not token:
            continue

        if token in TECHNICAL_LOC_BLACKLIST:
            return True

    return False


def process_loc_hit(text: str, hit: Treffer) -> Treffer | None:
    # Extrahiert zunächst den ursprünglichen Span
    input_span = text[hit.start:hit.ende]

    # Prüft, ob im Span eine Straße erkannt werden kann
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

    # Normalisiert den LOC-Span (z.B. Entfernen von Anhängen)
    normalized_loc = normalize_loc_span(text, hit)

    if normalized_loc is None:
        return None

    span = text[normalized_loc.start:normalized_loc.ende].strip()

    # Leere Spans verwerfen
    if not span:
        return None

    # Technische Begriffe (z.B. "Login-Service") verwerfen
    if _contains_technical_loc_term(span):
        return None

    # Code-/ID-artige Kennungen (z.B. "WL-2025") verwerfen
    if is_invalid_loc_id(span):
        return None

    # Plausibilitätsprüfung für Ortsnamen
    plausible = is_plausible_loc_span(span)

    if not plausible:
        return None

    # Validierten Treffer zurückgeben
    return normalized_loc