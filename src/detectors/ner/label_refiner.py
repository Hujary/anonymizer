from __future__ import annotations

import re
from typing import List

from core.typen import Treffer
from .postprocess_helpers.org.org_blacklists import ORG_LEGAL_SUFFIXES
from .postprocess_helpers.org.validate_org_span import is_valid_org_span


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

_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)

_ORG_SUFFIX_CHAIN_RE = re.compile(
    rf"""
    (?<![A-Za-zÄÖÜäöüß])

    (?P<suffix_chain>
        {_SUFFIX_TOKEN_PATTERN}
        (
            \s*&\s*Co\.?\s*
            {_SUFFIX_TOKEN_PATTERN}
        )?
    )

    (?=$|[^A-Za-zÄÖÜäöüß])
    """,
    re.IGNORECASE | re.VERBOSE,
)

_MISC_PER_TITLE_RE = re.compile(
    r"(?<![A-Za-zÄÖÜäöüß])(Herr|Herrn|Frau)(?=\s+[A-ZÄÖÜ])",
    re.IGNORECASE,
)


def _strip_outer_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


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


def _find_last_org_suffix_match(span: str) -> re.Match[str] | None:
    matches = list(_ORG_SUFFIX_CHAIN_RE.finditer(span))

    if not matches:
        return None

    return matches[-1]


def _looks_like_org_misc(text: str, start: int, end: int) -> bool:
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        return False

    raw_span = text[start:end]
    suffix_match = _find_last_org_suffix_match(raw_span)

    if suffix_match is None:
        return False

    suffix_end = suffix_match.end("suffix_chain")
    candidate_raw = raw_span[:suffix_end]

    if "\n" in candidate_raw or "\r" in candidate_raw:
        return False

    new_end = start + suffix_end
    new_start, new_end = _strip_outer_whitespace(text, start, new_end)

    if new_start >= new_end:
        return False

    candidate = text[new_start:new_end]

    if not is_valid_org_span(candidate):
        return False

    return True


def _looks_like_person_misc(text: str, start: int, end: int) -> bool:
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        return False

    raw_span = text[start:end]

    if "\n" in raw_span or "\r" in raw_span:
        return False

    if _MISC_PER_TITLE_RE.search(raw_span) is None:
        return False

    return True


def _refine_misc_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()

        if label != "MISC":
            out.append(h)
            continue

        if _looks_like_org_misc(text, h.start, h.ende):
            out.append(
                Treffer(
                    h.start,
                    h.ende,
                    "ORG",
                    h.source,
                    from_regex=h.from_regex,
                    from_ner=h.from_ner,
                )
            )
            continue

        if _looks_like_person_misc(text, h.start, h.ende):
            out.append(
                Treffer(
                    h.start,
                    h.ende,
                    "PER",
                    h.source,
                    from_regex=h.from_regex,
                    from_ner=h.from_ner,
                )
            )
            continue

    return out


def refine_ner_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()
        span = text[h.start:h.ende].strip()

        if not span:
            continue

        if label == "LOC":
            final_label = "STRASSE" if _looks_like_street(span) else "LOC"
        elif label == "PER":
            final_label = "PER"
        elif label == "ORG":
            final_label = "ORG"
        elif label == "MISC":
            final_label = "MISC"
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

    out = _refine_misc_labels(text, out)

    return out