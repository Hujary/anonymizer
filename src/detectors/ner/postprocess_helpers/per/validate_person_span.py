from __future__ import annotations

import re

from .per_blacklists import (
    ORG_INDICATOR_TOKENS_FOR_PER_FILTER,
    PER_BAD_SUFFIX_TOKENS,
    PER_BAD_TOKENS,
)
from .tokenize_person_span import tokenize_person_span


_PER_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PER_URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)
_PER_SPLIT_RE = re.compile(r"[\s\-_\/&]+")

_PER_DIRECT_REJECT_SPANS = {
    "bearbeiter",
    "bearbeiterin",
    "eintrittsdatum",
    "kontaktperson",
    "projektleiter",
    "projektleiterin",
    "ansprechpartner",
    "ansprechpartnerin",
    "support",
    "dashboard",
    "system",
    "service",
    "gateway",
    "backend",
    "frontend",
    "ticket",
    "status",
    "datum",
    "vertrag",
    "arbeitsvertrag",
    "zwischenupdate",
}

_DOMAIN_SUFFIXES = {
    ".de",
    ".com",
    ".net",
    ".org",
    ".info",
    ".biz",
    ".io",
    ".eu",
    ".co",
    ".local",
}


def _normalize_token(value: str) -> str:
    return value.strip().lower().strip(",.;:(){}[]\"'`„“‚‘-–—#_/\\|~+=")


def _contains_bad_token(value: str) -> bool:
    raw_parts = _PER_SPLIT_RE.split(value)

    for raw in raw_parts:
        token = _normalize_token(raw)

        if not token:
            continue

        if token in PER_BAD_TOKENS:
            return True

    return False


def _contains_org_indicator(value: str) -> bool:
    raw_parts = _PER_SPLIT_RE.split(value)

    for raw in raw_parts:
        token = _normalize_token(raw)

        if not token:
            continue

        if token in ORG_INDICATOR_TOKENS_FOR_PER_FILTER:
            return True

    return False


def _tokens_capitalized(tokens: list[str]) -> bool:
    if not tokens:
        return False

    for token in tokens:
        hyphen_parts = token.split("-")

        for hyphen_part in hyphen_parts:
            if not hyphen_part:
                return False

            dot_parts = hyphen_part.split(".")

            for dot_part in dot_parts:
                if not dot_part:
                    return False

                if not dot_part[0].isupper():
                    return False

    return True


def _bad_suffix(tokens: list[str]) -> bool:
    if not tokens:
        return True

    last = _normalize_token(tokens[-1])
    return last in PER_BAD_SUFFIX_TOKENS


def _is_valid_dotted_person_token(token: str) -> bool:
    value = token.strip()

    if not value:
        return False

    if "@" in value:
        return False

    lower_value = value.lower()

    if any(lower_value.endswith(suffix) for suffix in _DOMAIN_SUFFIXES):
        return False

    parts = value.split(".")

    if "" in parts:
        return False

    if len(parts) < 2 or len(parts) > 3:
        return False

    for part in parts:
        if not part.isalpha():
            return False

        if len(part) == 1:
            continue

        if len(part) < 2:
            return False

    return True


def _token_shape_valid(tokens: list[str]) -> bool:
    for token in tokens:
        hyphen_parts = token.split("-")

        for hyphen_part in hyphen_parts:
            if not hyphen_part:
                return False

            stripped = hyphen_part.strip()

            if not stripped:
                return False

            if "." in stripped:
                if not _is_valid_dotted_person_token(stripped):
                    return False
                continue

            if len(stripped) == 1 and stripped.isalpha():
                continue

            if len(stripped) < 2:
                return False

            if not stripped.isalpha():
                return False

    return True


def _has_internal_uppercase(token: str) -> bool:
    if len(token) <= 1:
        return False

    for ch in token[1:]:
        if ch.isupper():
            return True

    return False


def is_valid_person_span(span: str) -> bool:
    value = span.strip()

    if not value:
        return False

    if _normalize_token(value) in _PER_DIRECT_REJECT_SPANS:
        return False

    if _PER_EMAIL_RE.match(value):
        return False

    if _PER_URL_RE.match(value):
        return False

    if "\n" in value or "\r" in value:
        return False

    if any(char.isdigit() for char in value):
        return False

    if _contains_bad_token(value):
        return False

    if _contains_org_indicator(value):
        return False

    tokens = tokenize_person_span(value)

    if not tokens:
        return False

    if len(tokens) > 4:
        return False

    if len(tokens) == 1:
        token = tokens[0]

        if "." not in token and _has_internal_uppercase(token):
            return False

    if _bad_suffix(tokens):
        return False

    if not _token_shape_valid(tokens):
        return False

    if not _tokens_capitalized(tokens):
        return False

    return True