from __future__ import annotations

import re

from core.typen import Treffer

from .org_blacklists import ORG_BAD_TOKENS, ORG_LEGAL_SUFFIXES


_ORG_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ORG_URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)
_ORG_SPLIT_RE = re.compile(r"[\s\-_\/&]+")

_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)

_ORG_SUFFIX_NEAR_RIGHT_RE = re.compile(
    rf"""
    ^
    (?P<gap>[\s\.,;:()\[\]{{}}"'`-]{{0,3}})
    (?P<suffix>{_SUFFIX_TOKEN_PATTERN})
    (?=$|[\s\.,;:!?\)\]\}}"'`])
    """,
    re.IGNORECASE | re.VERBOSE,
)

_ORG_SUFFIX_IN_SPAN_RE = re.compile(
    rf"""
    (?P<suffix>{_SUFFIX_TOKEN_PATTERN})
    (?=$|[\s\.,;:!?\)\]\}}"'`])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalize_token(value: str) -> str:
    return value.strip().lower().strip(",.;:(){}[]\"'`„“‚‘-–—")


def _looks_like_email(value: str) -> bool:
    return _ORG_EMAIL_RE.match(value.strip()) is not None


def _looks_like_url(value: str) -> bool:
    return _ORG_URL_RE.match(value.strip()) is not None


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


def _extend_span_to_right_suffix(text: str, start: int, end: int) -> tuple[int, int]:
    tail = text[end:end + 16]
    match = _ORG_SUFFIX_NEAR_RIGHT_RE.match(tail)

    if match is None:
        return start, end

    suffix_end = end + match.end("suffix")
    return start, suffix_end


def _cut_span_at_suffix(text: str, start: int, end: int) -> tuple[int, int]:
    span = text[start:end]
    matches = list(_ORG_SUFFIX_IN_SPAN_RE.finditer(span))

    if not matches:
        return start, end

    last = matches[-1]
    cut_end = start + last.end("suffix")
    return start, cut_end


def _contains_bad_org_token(span: str) -> bool:
    raw_parts = _ORG_SPLIT_RE.split(span)

    for raw in raw_parts:
        token = _normalize_token(raw)
        if not token:
            continue

        if token in ORG_BAD_TOKENS:
            return True

    return False


def _is_obviously_invalid_org(span: str) -> bool:
    value = span.strip()

    if not value:
        return True

    if _looks_like_email(value):
        return True

    if _looks_like_url(value):
        return True

    if _contains_bad_org_token(value):
        return True

    return False


def process_org_hit(text: str, hit: Treffer) -> Treffer | None:
    start, end = _cleanup_outer_whitespace(text, hit.start, hit.ende)

    if start >= end:
        return None

    start, end = _extend_span_to_right_suffix(text, start, end)
    start, end = _cut_span_at_suffix(text, start, end)
    start, end = _cleanup_trailing_punctuation(text, start, end)
    start, end = _cleanup_outer_whitespace(text, start, end)

    if start >= end:
        return None

    span = text[start:end]

    if _is_obviously_invalid_org(span):
        return None

    return Treffer(
        start,
        end,
        "ORG",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )