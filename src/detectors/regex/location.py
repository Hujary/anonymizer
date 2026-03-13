from __future__ import annotations

import re
from typing import Iterable, Tuple


_PLZ_RE = re.compile(
    r"(?<!\d)(?:D[-\s])?(?P<plz>\d{5})(?!\d)"
)

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

_GROSSWORT = r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß]*(?:-[A-ZÄÖÜ][A-Za-zÄÖÜäöüß]*)*"
_HAUSNUMMER = r"\d{1,4}[A-Za-z]?(?:\s*[-/]\s*\d{1,4}[A-Za-z]?)?"

_STRASSE_RE = re.compile(
    rf"""
    (?<![A-Za-zÄÖÜäöüß0-9_])

    (?P<street>
        (?:
            (?:
                {_GROSSWORT}(?:\s+{_GROSSWORT}){{0,2}}
                \s+
                {_SUFFIX_CI}
            )
            |
            (?:
                {_GROSSWORT}{_SUFFIX_CI}
            )
        )
        \s+
        (?P<hausnummer>{_HAUSNUMMER})
    )

    (?![A-Za-zÄÖÜäöüß0-9_])
    """,
    re.VERBOSE,
)


def _valid_plz_boundary(text: str, start: int, end: int) -> bool:
    allowed_left = set(" \t\r\n,;:([{\"'")
    allowed_right = set(" \t\r\n,;:.)]}/\"'")

    prev = text[start - 1] if start > 0 else ""
    nxt = text[end] if end < len(text) else ""

    if prev and prev not in allowed_left:
        return False
    if nxt and nxt not in allowed_right:
        return False
    if start > 0 and text[start - 1] in "-_/":
        return False

    return True


def _valid_street_boundary(text: str, start: int, end: int) -> bool:
    prev = text[start - 1] if start > 0 else ""
    nxt = text[end] if end < len(text) else ""

    if prev and (prev.isalnum() or prev == "_"):
        return False
    if nxt and (nxt.isalnum() or nxt == "_"):
        return False

    return True


def _looks_like_street_candidate(value: str) -> bool:
    if "\n" in value or "\r" in value:
        return False

    if len(value) > 50:
        return False

    if "," in value or ";" in value or ":" in value:
        return False

    parts = value.split()
    if len(parts) < 2:
        return False

    digit_count = sum(ch.isdigit() for ch in value)
    if digit_count == 0:
        return False

    first = parts[0]
    if not first or not first[0].isupper():
        return False

    return True


def finde_location(text: str) -> Iterable[Tuple[int, int, str]]:
    for m in _PLZ_RE.finditer(text):
        s, e = m.start("plz"), m.end("plz")
        if not _valid_plz_boundary(text, s, e):
            continue
        yield (s, e, "PLZ")

    for m in _STRASSE_RE.finditer(text):
        s, e = m.start("street"), m.end("street")
        if not _valid_street_boundary(text, s, e):
            continue

        candidate = text[s:e]
        if not _looks_like_street_candidate(candidate):
            continue

        yield (s, e, "STRASSE")