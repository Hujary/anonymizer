from __future__ import annotations

import re


# Typische technische oder organisatorische Kennungen:
# WL-2025
# PRJ-77
# CASE-1234
# ID-2025-77
# TKT-991
#
# Bewusst relativ eng gehalten:
# - beginnt mit Großbuchstabenblock
# - dann mindestens ein Zahlenblock
# - optional weitere Blöcke
_LOC_TECHNICAL_ID_RE = re.compile(
    r"""
    ^
    [A-Z]{1,10}
    (?:-[A-Z0-9]{1,10})*
    -
    \d{1,10}
    (?:-[A-Z0-9]{1,10})*
    $
    """,
    re.VERBOSE,
)


# Allgemeiner Code-/Kennungsfall ohne Leerzeichen:
# ABC123
# WL2025
# PRJ77
#
# Absichtlich restriktiv, damit normale Ortsnamen nicht betroffen sind.
_LOC_COMPACT_CODE_RE = re.compile(
    r"""
    ^
    (?=.*[A-ZÄÖÜ])
    (?=.*\d)
    [A-ZÄÖÜ0-9]{4,20}
    $
    """,
    re.VERBOSE,
)


def _looks_like_technical_id_pattern(value: str) -> bool:
    if _LOC_TECHNICAL_ID_RE.fullmatch(value):
        return True

    if _LOC_COMPACT_CODE_RE.fullmatch(value):
        return True

    return False


def _looks_like_single_code_token(value: str) -> bool:
    parts = value.split()

    if len(parts) != 1:
        return False

    token = parts[0]

    if _looks_like_technical_id_pattern(token):
        return True

    return False


def _has_mixed_uppercase_digit_code_shape(value: str) -> bool:
    token = value.strip()

    if " " in token:
        return False

    has_digit = any(ch.isdigit() for ch in token)
    has_upper = any(ch.isupper() for ch in token)
    has_hyphen = "-" in token or "_" in token or "/" in token

    if has_digit and has_upper and has_hyphen:
        return True

    return False


def is_invalid_loc_id(span: str) -> bool:
    value = span.strip()

    if not value:
        return True

    if "\n" in value or "\r" in value:
        return True

    if _looks_like_single_code_token(value):
        return True

    if _has_mixed_uppercase_digit_code_shape(value):
        return True

    return False