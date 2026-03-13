from __future__ import annotations

import re
from typing import List

from core.typen import Treffer


STRASSEN_SUFFIXE: tuple[str, ...] = (
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
)

_GENERISCHE_SUFFIX_WOERTER = {
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

_HAUSNUMMER_IM_SPAN_RE = re.compile(
    r"[A-Za-z]?\d{1,4}[A-Za-z]?(?:\s*[-/]\s*[A-Za-z]?\d{1,4}[A-Za-z]?)?$"
)

_TOKEN_SPLIT_RE = re.compile(r"[\s\/]+")


def _normalize_token(text: str) -> str:
    value = text.strip()
    value = re.sub(r"[,\.;:]+$", "", value)
    return value


def _normalize_token_lc(text: str) -> str:
    return _normalize_token(text).lower()


def _tokenize_span_raw(span: str) -> list[str]:
    parts = _TOKEN_SPLIT_RE.split(span.strip())
    out: list[str] = []

    for part in parts:
        token = _normalize_token(part)
        if token:
            out.append(token)

    return out


def _ends_with_street_suffix(token: str) -> bool:
    value = _normalize_token_lc(token)
    return any(value.endswith(suffix) for suffix in STRASSEN_SUFFIXE)


def _has_capitalized_name_part(token: str) -> bool:
    value = _normalize_token(token)

    if not value:
        return False

    for part in value.split("-"):
        if not part:
            continue
        if part[0].isupper():
            return True

    return False


def _is_generic_street_word(token: str) -> bool:
    value = _normalize_token_lc(token)
    return value in _GENERISCHE_SUFFIX_WOERTER


def _looks_like_street(span: str) -> bool:
    value = span.strip()

    if not value:
        return False

    if "\n" in value or "\r" in value:
        return False

    tokens = _tokenize_span_raw(value)

    if not tokens:
        return False

    has_house_number = _HAUSNUMMER_IM_SPAN_RE.fullmatch(tokens[-1]) is not None
    street_tokens = tokens[:-1] if has_house_number else tokens

    if not street_tokens:
        return False

    if len(street_tokens) > 4:
        return False

    joined = " ".join(street_tokens)

    if joined.lower() == joined:
        return False

    last = street_tokens[-1]
    if not _ends_with_street_suffix(last):
        return False

    if len(street_tokens) == 1:
        if _is_generic_street_word(last):
            return False
        return _has_capitalized_name_part(last)

    name_tokens = street_tokens[:-1]

    if not name_tokens:
        return False

    for token in name_tokens:
        if not _has_capitalized_name_part(token):
            return False

    return True


def refine_ner_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()
        span = text[h.start:h.ende].strip()

        if not span:
            continue

        if label != "LOC":
            continue

        final_label = "STRASSE" if _looks_like_street(span) else "LOC"

        out.append(
            Treffer(
                h.start,
                h.ende,
                final_label,
                h.source,
                from_regex=h.from_regex,
                from_ner=h.from_ner,
            )
        )

    return out