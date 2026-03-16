from __future__ import annotations

import re
from typing import List

from core.typen import Treffer

from .refine_misc_labels import refine_misc_labels


# Bekannte Straßensuffixe im deutschen Sprachraum.
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

# Generische reine Suffixwörter ohne individuellen Straßenname davor.
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

# Hausnummern wie 12, 12a, A12 oder 12-14 am Ende des Spans.
_HAUSNUMMER_IM_SPAN_RE = re.compile(
    r"[A-Za-z]?\d{1,4}[A-Za-z]?(?:\s*[-/]\s*[A-Za-z]?\d{1,4}[A-Za-z]?)?$"
)

# Tokenisierung entlang von Leerzeichen oder Slash.
_TOKEN_SPLIT_RE = re.compile(r"[\s\/]+")


def _normalize_token(text: str) -> str:
    # Randzeichen am Ende vereinheitlichen.
    value = text.strip()
    value = re.sub(r"[,\.;:]+$", "", value)
    return value


def _normalize_token_lc(text: str) -> str:
    # Token normieren und in Kleinschreibung überführen.
    return _normalize_token(text).lower()


def _tokenize_span_raw(span: str) -> list[str]:
    # Span in bereinigte Einzelteile zerlegen.
    parts = _TOKEN_SPLIT_RE.split(span.strip())
    out: list[str] = []

    for part in parts:
        token = _normalize_token(part)
        if token:
            out.append(token)

    return out


def _ends_with_street_suffix(token: str) -> bool:
    # Prüfen, ob ein Token mit einem Straßensuffix endet.
    value = _normalize_token_lc(token)
    return any(value.endswith(suffix) for suffix in STRASSEN_SUFFIXE)


def _has_capitalized_name_part(token: str) -> bool:
    # Prüfen, ob mindestens ein Namensbestandteil groß beginnt.
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
    # Reines Gattungswort wie "Straße" oder "Weg" erkennen.
    value = _normalize_token_lc(token)
    return value in _GENERISCHE_SUFFIX_WOERTER


def _looks_like_street(span: str) -> bool:
    # Heuristische Prüfung, ob ein LOC-Span eher eine Straße darstellt.
    value = span.strip()

    if not value:
        return False

    # Mehrzeilige Spans werden nicht als Straße interpretiert.
    if "\n" in value or "\r" in value:
        return False

    tokens = _tokenize_span_raw(value)

    if not tokens:
        return False

    # Optionale Hausnummer am Ende separat behandeln.
    has_house_number = _HAUSNUMMER_IM_SPAN_RE.fullmatch(tokens[-1]) is not None
    street_tokens = tokens[:-1] if has_house_number else tokens

    if not street_tokens:
        return False

    # Zu lange Spans werden verworfen.
    if len(street_tokens) > 4:
        return False

    joined = " ".join(street_tokens)

    # Vollständig kleingeschriebene Kandidaten werden verworfen.
    if joined.lower() == joined:
        return False

    last = street_tokens[-1]

    # Letztes Token muss ein Straßensuffix tragen.
    if not _ends_with_street_suffix(last):
        return False

    # Einzeltoken wie "Bahnhofstraße" sind erlaubt, reine Gattungswörter nicht.
    if len(street_tokens) == 1:
        if _is_generic_street_word(last):
            return False
        return _has_capitalized_name_part(last)

    # Vor dem Suffix muss ein plausibler Namensanteil stehen.
    name_tokens = street_tokens[:-1]

    if not name_tokens:
        return False

    for token in name_tokens:
        if not _has_capitalized_name_part(token):
            return False

    return True


def refine_ner_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    # Rohlabels aus der NER-Erkennung in domänenspezifische Labels überführen.
    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()
        span = text[h.start:h.ende].strip()

        # Leere Spans werden verworfen.
        if not span:
            continue

        # LOC wird bei Straßenheuristik zu STRASSE umklassifiziert.
        if label == "LOC":
            final_label = "STRASSE" if _looks_like_street(span) else "LOC"

        # PER bleibt zunächst unverändert.
        elif label == "PER":
            final_label = "PER"

        # ORG bleibt zunächst unverändert.
        elif label == "ORG":
            final_label = "ORG"

        # MISC wird in einem nachgelagerten Schritt weiter geprüft.
        elif label == "MISC":
            final_label = "MISC"

        # Alle anderen Labels werden in dieser Stufe ignoriert.
        else:
            continue

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

    # MISC-Spans anschließend separat in ORG oder PER umklassifizieren.
    out = refine_misc_labels(text, out)

    return out