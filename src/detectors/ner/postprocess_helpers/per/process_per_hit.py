from __future__ import annotations

import re

from core.typen import Treffer

from .per_blacklists import (
    ORG_INDICATOR_TOKENS_FOR_PER_FILTER,
    PER_BAD_SUFFIX_TOKENS,
    PER_BAD_TOKENS,
)


_PER_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PER_URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)
_PER_TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)?")
_PER_SPLIT_RE = re.compile(r"[\s\-_\/&]+")


def _normalize_token(value: str) -> str:
    return value.strip().lower().strip(",.;:(){}[]\"'`„“‚‘-–—")


def _cleanup_outer_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


def _cleanup_trailing_punctuation(text: str, start: int, end: int) -> tuple[int, int]:
    trailing_chars = " \t\r\n,.;:!?)]}\"'`"
    while end > start and text[end - 1] in trailing_chars:
        end -= 1
    return start, end


def _looks_like_email(value: str) -> bool:
    return _PER_EMAIL_RE.match(value.strip()) is not None


def _looks_like_url(value: str) -> bool:
    return _PER_URL_RE.match(value.strip()) is not None


def _contains_newline(value: str) -> bool:
    return "\n" in value or "\r" in value


def _tokenize_person_span(value: str) -> list[str]:
    return _PER_TOKEN_RE.findall(value)


def _contains_bad_per_token(value: str) -> bool:
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


def _all_name_tokens_capitalized(tokens: list[str]) -> bool:
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


def _ends_with_bad_suffix_token(tokens: list[str]) -> bool:
    if not tokens:
        return False

    last = _normalize_token(tokens[-1])
    return last in PER_BAD_SUFFIX_TOKENS


def _is_valid_person_span(value: str) -> bool:
    span = value.strip()

    if not span:
        return False

    if _looks_like_email(span):
        return False

    if _looks_like_url(span):
        return False

    if _contains_newline(span):
        return False

    if any(ch.isdigit() for ch in span):
        return False

    if _contains_bad_per_token(span):
        return False

    if _contains_org_indicator(span):
        return False

    tokens = _tokenize_person_span(span)

    if not tokens:
        return False

    if len(tokens) > 2:
        return False

    if len(tokens) == 1:
        token = tokens[0]

        if len(token) < 2:
            return False

        if _ends_with_bad_suffix_token(tokens):
            return False

        return _all_name_tokens_capitalized(tokens)

    if len(tokens) == 2:
        if _ends_with_bad_suffix_token(tokens):
            return False

        return _all_name_tokens_capitalized(tokens)

    return False


def process_per_hit(text: str, hit: Treffer) -> Treffer | None:
    start, end = _cleanup_outer_whitespace(text, hit.start, hit.ende)
    start, end = _cleanup_trailing_punctuation(text, start, end)
    start, end = _cleanup_outer_whitespace(text, start, end)

    if start >= end:
        return None

    span = text[start:end]

    if not _is_valid_person_span(span):
        return None

    return Treffer(
        start,
        end,
        "PER",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )