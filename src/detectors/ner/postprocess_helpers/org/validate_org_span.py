from __future__ import annotations

import re

from .org_blacklists import ORG_BAD_TOKENS


# Regex zur Erkennung von E-Mail-Adressen
_ORG_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Regex zur Erkennung von URLs
_ORG_URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)

# Token-Splitting für Organisationsnamen
_ORG_SPLIT_RE = re.compile(r"[\s\-_\/&]+")


def _normalize_token(value: str) -> str:
    # Normalisiert Tokens für Vergleich mit Blacklists
    # Entfernt Whitespaces, Satzzeichen und konvertiert zu lowercase
    return value.strip().lower().strip(",.;:(){}[]\"'`„“‚‘-–—")


def _contains_bad_org_token(span: str) -> bool:
    # Prüft, ob ein Token aus dem Span in der Organisations-Blacklist enthalten ist
    raw_parts = _ORG_SPLIT_RE.split(span)

    for raw in raw_parts:
        token = _normalize_token(raw)

        if not token:
            continue

        if token in ORG_BAD_TOKENS:
            return True

    return False


def is_valid_org_span(span: str) -> bool:
    # Validiert, ob ein Textspan plausibel eine Organisation darstellt
    value = span.strip()

    # Leere Spans verwerfen
    if not value:
        return False

    # E-Mail-Adressen sind keine Organisationen
    if _ORG_EMAIL_RE.match(value):
        return False

    # URLs sind ebenfalls keine Organisationen
    if _ORG_URL_RE.match(value):
        return False

    # Spans mit unerwünschten Tokens verwerfen
    if _contains_bad_org_token(value):
        return False

    # Span ist valide
    return True