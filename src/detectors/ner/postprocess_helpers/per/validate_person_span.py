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
}

_PER_TITLE_TOKENS = {
    "herr",
    "herrn",
    "frau",
    "dr",
    "prof",
    "professor",
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
        parts = token.split("-")

        for part in parts:
            if not part:
                return False

            if not part[0].isupper():
                return False

    return True


def _bad_suffix(tokens: list[str]) -> bool:
    if not tokens:
        return True

    last = _normalize_token(tokens[-1])
    return last in PER_BAD_SUFFIX_TOKENS


def _contains_title_token(tokens: list[str]) -> bool:
    for token in tokens:
        normalized = _normalize_token(token)
        if normalized in _PER_TITLE_TOKENS:
            return True
    return False


def _token_shape_valid(tokens: list[str]) -> bool:
    for token in tokens:
        parts = token.split("-")

        for part in parts:
            if not part:
                return False
            if len(part) < 2:
                return False
            if not part.isalpha():
                return False

    return True


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

    if len(tokens) > 2:
        return False

    if _contains_title_token(tokens):
        return False

    if _bad_suffix(tokens):
        return False

    if not _token_shape_valid(tokens):
        return False

    if not _tokens_capitalized(tokens):
        return False

    return True