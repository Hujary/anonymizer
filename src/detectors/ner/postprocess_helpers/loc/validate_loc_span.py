from __future__ import annotations

from ..shared.normalize_text import normalize_token


_LOC_GENERIC_WORDS = {
    "straße",
    "strasse",
    "str.",
    "str",
    "weg",
    "allee",
    "gasse",
    "platz",
    "ring",
    "ufer",
    "damm",
    "stieg",
    "zeile",
    "chaussee",
    "pfad",
    "steig",
    "markt",
    "wall",
    "kai",
}


def is_plausible_loc_span(span: str) -> bool:
    value = span.strip()

    if not value:
        return False

    if "\n" in value or "\r" in value:
        return False

    if len(value) > 40:
        return False

    if "," in value or ";" in value or ":" in value:
        return False

    if not any(ch.isalpha() for ch in value):
        return False

    if value.lower() == value:
        return False

    tokens = value.split()
    if not tokens:
        return False

    if len(tokens) > 4:
        return False

    if len(tokens) == 1:
        token = normalize_token(tokens[0])
        if token in _LOC_GENERIC_WORDS:
            return False

    return True