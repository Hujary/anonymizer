from __future__ import annotations

import re

from ..shared.normalize_text import normalize_whitespace
from .extend_street_house_number import find_direct_house_number


_STRASSEN_SUFFIXE = (
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

_STRASSEN_SUFFIX_PATTERN = "|".join(re.escape(x) for x in _STRASSEN_SUFFIXE)
_SUFFIX_CI = rf"(?i:(?:{_STRASSEN_SUFFIX_PATTERN}))"
_WORT = r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß]*"
_WORTFOLGE = rf"{_WORT}(?:-{_WORT})*"
_HAUSNUMMER = r"\d{1,4}[A-Za-z]?(?:\s*[-/]\s*\d{1,4}[A-Za-z]?)?"

_STREET_CORE = rf"""
(?:
    (?:
        {_WORTFOLGE}(?:\s+{_WORTFOLGE}){{0,2}}
        (?:\s+|-)
        {_SUFFIX_CI}
    )
    |
    (?:
        {_WORTFOLGE}{_SUFFIX_CI}
    )
)
"""

_STRASSE_CORE_RE = re.compile(
    rf"""
    (?<![A-Za-zÄÖÜäöüß0-9_])
    (?P<street>{_STREET_CORE})
    (?![A-Za-zÄÖÜäöüß0-9_])
    """,
    re.VERBOSE,
)

_STRASSE_FULL_RE = re.compile(
    rf"""
    ^
    (?P<street>
        {_STREET_CORE}
        (?:\s+(?P<hausnummer>{_HAUSNUMMER}))?
    )
    $
    """,
    re.VERBOSE,
)


def _is_valid_street_span(span: str) -> bool:
    value = span.strip()

    if not value:
        return False

    if "\n" in value or "\r" in value:
        return False

    if len(value) > 60:
        return False

    if "," in value or ";" in value or ":" in value:
        return False

    return _STRASSE_FULL_RE.fullmatch(value) is not None


def extract_street_span_from_loc(text: str, start: int, end: int) -> tuple[int, int] | None:
    raw_span = text[start:end]

    if not raw_span.strip():
        return None

    lines = raw_span.splitlines()
    if not lines:
        return None

    first_line_original = lines[0]
    first_line = normalize_whitespace(first_line_original)

    if not first_line:
        return None

    match = _STRASSE_CORE_RE.search(first_line)
    if match is None:
        return None

    normalized_match = match.group("street")
    original_rel_start = first_line_original.find(normalized_match)
    if original_rel_start < 0:
        original_rel_start = 0

    abs_start = start + original_rel_start
    abs_end = abs_start + len(normalized_match)

    house_number_span = find_direct_house_number(text, abs_end)
    if house_number_span is not None:
        _, house_number_end = house_number_span
        candidate = text[abs_start:house_number_end].strip()
        if _is_valid_street_span(candidate):
            return abs_start, house_number_end

    candidate = text[abs_start:abs_end].strip()
    if _is_valid_street_span(candidate):
        return abs_start, abs_end

    return None