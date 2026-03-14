from __future__ import annotations

import re

from .org_blacklists import ORG_BAD_TOKENS


_ORG_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ORG_URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)
_ORG_SPLIT_RE = re.compile(r"[\s\-_\/&]+")


def _normalize_token(value: str) -> str:
    return value.strip().lower().strip(",.;:(){}[]\"'`„“‚‘-–—")


def _contains_bad_org_token(span: str) -> bool:
    parts = _ORG_SPLIT_RE.split(span)

    for raw in parts:
        token = _normalize_token(raw)

        if not token:
            continue

        if token in ORG_BAD_TOKENS:
            return True

    return False


def is_valid_org_span(span: str) -> bool:
    value = span.strip()

    if not value:
        return False

    if _ORG_EMAIL_RE.match(value):
        return False

    if _ORG_URL_RE.match(value):
        return False

    if "\n" in value or "\r" in value:
        return False

    if "•" in value:
        return False

    if len(value) <= 2:
        return False

    if _contains_bad_org_token(value):
        return False

    return True