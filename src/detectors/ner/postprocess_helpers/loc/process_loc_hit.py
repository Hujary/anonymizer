from __future__ import annotations

import re

from core.typen import Treffer

from .extract_street_span import extract_street_span_from_loc
from .normalize_loc_span import normalize_loc_span
from .validate_loc_span import is_plausible_loc_span
from .loc_blacklists import TECHNICAL_LOC_BLACKLIST
from .loc_id_validator import is_invalid_loc_id


# Tokenisierung für Blacklist-Prüfungen.
# Trennt u. a. "Monitoring-Service" in einzelne Bestandteile.
_LOC_TOKEN_SPLIT_RE = re.compile(r"[\s\-_\/]+")


def _normalize_blacklist_token(token: str) -> str:
    # Vergleichstokens vereinheitlichen:
    # Leerzeichen entfernen, Kleinschreibung erzwingen, typische Randzeichen abschneiden.
    strip_chars = ",.;:(){}[]\"'`„“‚‘-–—"
    return token.strip().lower().strip(strip_chars)


def _contains_technical_loc_term(span: str) -> bool:
    # Ein LOC-Span wird verworfen, wenn er technische / systemische Begriffe enthält,
    # die mit hoher Wahrscheinlichkeit keine echten Orte sind.
    raw_parts = _LOC_TOKEN_SPLIT_RE.split(span)

    for raw in raw_parts:
        token = _normalize_blacklist_token(raw)

        if not token:
            continue

        if token in TECHNICAL_LOC_BLACKLIST:
            return True

    return False


def process_loc_hit(text: str, hit: Treffer) -> Treffer | None:
    # Bereits als STRASSE klassifizierte Treffer laufen ebenfalls hier hinein.
    # In diesem Fall wird nur noch validiert bzw. die Hausnummer-Erweiterung geprüft.
    street_span = extract_street_span_from_loc(text, hit.start, hit.ende)

    # Wenn aus dem Treffer eine Straße extrahiert werden kann,
    # wird das Ergebnis explizit als STRASSE zurückgegeben.
    # Dabei darf der Treffer auch über den ursprünglichen Span hinaus
    # auf die direkt folgende Hausnummer erweitert werden.
    if street_span is not None:
        start, end = street_span

        return Treffer(
            start,
            end,
            "STRASSE",
            hit.source,
            from_regex=hit.from_regex,
            from_ner=hit.from_ner,
        )

    # Wenn keine Straße vorliegt, wird der Treffer als normaler LOC-Kandidat weiterbehandelt.
    normalized_loc = normalize_loc_span(text, hit)

    # Unbrauchbare oder vollständig weggefallene Spans werden verworfen.
    if normalized_loc is None:
        return None

    span = text[normalized_loc.start:normalized_loc.ende].strip()

    # Leere Spans sind nach Normalisierung nicht mehr verwertbar.
    if not span:
        return None

    # Technische Begriffe wie Services, Systeme, IDs etc. sollen nicht als LOC durchgehen.
    if _contains_technical_loc_term(span):
        return None

    # Code- oder ID-artige Spans wie WL-2025 sollen ebenfalls nicht als LOC gelten.
    if is_invalid_loc_id(span):
        return None

    # Finale Plausibilitätsprüfung für echte Ortsangaben.
    if not is_plausible_loc_span(span):
        return None

    # Treffer bleibt ein normaler Orts-Treffer.
    return Treffer(
        normalized_loc.start,
        normalized_loc.ende,
        "LOC",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )