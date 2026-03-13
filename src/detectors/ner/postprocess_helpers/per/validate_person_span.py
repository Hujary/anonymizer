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


def _normalize_token(value: str) -> str:
    return value.strip().lower().strip(",.;:(){}[]\"'`„“‚‘-–—")


def _contains_bad_token(value: str) -> bool:
    raw_parts = _PER_SPLIT_RE.split(value)

    for raw in raw_parts:
        token = _normalize_token(raw)

        if token in PER_BAD_TOKENS:
            return True

    return False


def _contains_org_indicator(value: str) -> bool:
    raw_parts = _PER_SPLIT_RE.split(value)

    for raw in raw_parts:
        token = _normalize_token(raw)

        if token in ORG_INDICATOR_TOKENS_FOR_PER_FILTER:
            return True

    return False


def _tokens_capitalized(tokens: list[str]) -> bool:
    for token in tokens:
        parts = token.split("-")

        for part in parts:
            if not part[0].isupper():
                return False

    return True


def _bad_suffix(tokens: list[str]) -> bool:
    last = _normalize_token(tokens[-1])
    return last in PER_BAD_SUFFIX_TOKENS


def is_valid_person_span(span: str) -> bool:
    value = span.strip()

    if not value:
        return False

    if _PER_EMAIL_RE.match(value):
        return False

    if _PER_URL_RE.match(value):
        return False

    if "\n" in value:
        return False

    if any(c.isdigit() for c in value):
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

    if _bad_suffix(tokens):
        return False

    if not _tokens_capitalized(tokens):
        return False

    return True