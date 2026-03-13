from __future__ import annotations

import re
from typing import List

from core.typen import Treffer


_HAUSNUMMER_DIREKT_RE = re.compile(
    r"""
    ^
    (?P<ws>\s+)
    (?P<hausnummer>
        \d{1,4}[A-Za-z]?
        (?:\s*[-/]\s*\d{1,4}[A-Za-z]?)?
    )
    """,
    re.VERBOSE,
)

_PLZ_AM_ANFANG_RE = re.compile(
    r"""
    ^
    (?:
        D[-\s]?
    )?
    (?P<plz>\d{5})
    (?P<sep>\s+)
    """,
    re.VERBOSE,
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

_LOC_GENERIC_WORDS = {
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
    (?P<street>
        {_STREET_CORE}
    )
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


def _deduplicate_hits(hits: List[Treffer]) -> List[Treffer]:
    seen: set[tuple[int, int, str]] = set()
    out: List[Treffer] = []

    for h in hits:
        key = (h.start, h.ende, h.label)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)

    return out


def _find_direct_house_number(text: str, end_pos: int) -> tuple[int, int] | None:
    tail = text[end_pos:]
    m = _HAUSNUMMER_DIREKT_RE.match(tail)

    if not m:
        return None

    ws = m.group("ws")
    hausnummer = m.group("hausnummer")

    if not hausnummer:
        return None

    start = end_pos + len(ws)
    ende = start + len(hausnummer)
    return start, ende


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

    if not _STRASSE_FULL_RE.fullmatch(value):
        return False

    return True


def _normalize_token(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"[,\.;:]+$", "", value)
    return value


def _is_plausible_loc_span(span: str) -> bool:
    value = span.strip()

    if not value:
        return False

    if "\n" in value or "\r" in value:
        return False

    if len(value) > 40:
        return False

    if "," in value or ";" in value or ":" in value:
        return False

    if not any(ch.isalpha() for ch in value):
        return False

    if value.lower() == value:
        return False

    tokens = value.split()
    if not tokens:
        return False

    if len(tokens) > 4:
        return False

    if len(tokens) == 1:
        token = _normalize_token(tokens[0])
        if token in _LOC_GENERIC_WORDS:
            return False

    return True


def _extract_street_from_line(line: str) -> tuple[int, int] | None:
    m = _STRASSE_CORE_RE.search(line)
    if not m:
        return None

    return m.start("street"), m.end("street")


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _strip_leading_plz_from_loc_segment(segment: str) -> tuple[int, str]:
    """
    Entfernt eine führende PLZ aus einem LOC-Kandidaten.
    Gibt (offset_im_segment, bereinigter_text) zurück.
    """
    m = _PLZ_AM_ANFANG_RE.match(segment)
    if not m:
        return 0, segment.strip()

    offset = m.end()
    cleaned = segment[offset:].strip()
    return offset, cleaned


def _postprocess_loc_span(text: str, start: int, ende: int) -> tuple[int, int] | None:
    raw_span = text[start:ende]

    if not raw_span.strip():
        return None

    lines = raw_span.splitlines()
    if not lines:
        return None

    first_line_original = lines[0]
    first_line = _normalize_whitespace(first_line_original)

    if not first_line:
        return None

    street_rel = _extract_street_from_line(first_line)
    if street_rel is not None:
        rel_start, rel_end = street_rel

        normalized_match = first_line[rel_start:rel_end]

        original_rel_start = first_line_original.find(normalized_match)
        if original_rel_start < 0:
            original_rel_start = 0

        abs_start = start + original_rel_start
        abs_end = abs_start + len(normalized_match)

        hausnummer_span = _find_direct_house_number(text, abs_end)
        if hausnummer_span is not None:
            _, hausnummer_ende = hausnummer_span
            candidate = text[abs_start:hausnummer_ende].strip()
            if _is_valid_street_span(candidate):
                return abs_start, hausnummer_ende

        candidate = text[abs_start:abs_end].strip()
        if _is_valid_street_span(candidate):
            return abs_start, abs_end

    stripped_first_line = first_line_original.strip()
    if not stripped_first_line:
        return None

    line_offset = raw_span.find(first_line_original)
    base_abs_start = start + line_offset
    base_abs_end = base_abs_start + len(first_line_original.rstrip())

    while base_abs_start < base_abs_end and text[base_abs_start].isspace():
        base_abs_start += 1
    while base_abs_end > base_abs_start and text[base_abs_end - 1].isspace():
        base_abs_end -= 1

    if base_abs_start >= base_abs_end:
        return None

    candidate_raw = text[base_abs_start:base_abs_end]
    plz_offset, candidate_clean = _strip_leading_plz_from_loc_segment(candidate_raw)

    if not candidate_clean:
        return None

    abs_start = base_abs_start + plz_offset
    abs_end = abs_start + len(candidate_clean)

    if abs_start >= abs_end:
        return None

    return abs_start, abs_end


def postprocess_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()

        if label != "LOC":
            continue

        repaired = _postprocess_loc_span(text, h.start, h.ende)
        if repaired is None:
            continue

        start, ende = repaired
        span = text[start:ende].strip()

        if not span:
            continue

        out.append(
            Treffer(
                start,
                ende,
                label,
                h.source,
                from_regex=h.from_regex,
                from_ner=h.from_ner,
            )
        )

    out = _deduplicate_hits(out)

    final_out: List[Treffer] = []

    for h in out:
        span = text[h.start:h.ende].strip()
        if not _is_plausible_loc_span(span):
            continue
        final_out.append(h)

    final_out.sort(key=lambda t: (t.start, t.ende, t.label))
    return final_out