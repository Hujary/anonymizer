from __future__ import annotations

import re
from typing import List

from core.typen import Treffer

from .postprocess_helpers.org.validate_org_span import is_valid_org_span
from .postprocess_helpers.org.org_blacklists import ORG_LEGAL_SUFFIXES


# Längere Suffixe zuerst, damit z. B. "GmbH & Co. KG" korrekt erkannt wird.
_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)

# Erlaubt einen Rechtsträgerzusatz optional mit "& Co."-Kette.
_ORG_SUFFIX_CHAIN_RE = re.compile(
    rf"""
    (?<![A-Za-zÄÖÜäöüß])

    (?P<suffix_chain>
        {_SUFFIX_TOKEN_PATTERN}
        (
            \s*&\s*Co\.?\s*
            {_SUFFIX_TOKEN_PATTERN}
        )?
    )

    (?=$|[^A-Za-zÄÖÜäöüß])
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Ein MISC-Span wird nur dann als Person gewertet, wenn eine typische Anrede enthalten ist.
_MISC_PER_TITLE_RE = re.compile(
    r"(?<![A-Za-zÄÖÜäöüß])(Herr|Herrn|Frau)(?=\s+[A-ZÄÖÜ])",
    re.IGNORECASE,
)


def _strip_outer_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    # Führende Leerzeichen entfernen.
    while start < end and text[start].isspace():
        start += 1

    # Nachgestellte Leerzeichen entfernen.
    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


def _find_last_org_suffix_match(span: str) -> re.Match[str] | None:
    # Letzten passenden Rechtsträgerzusatz im Span bestimmen.
    matches = list(_ORG_SUFFIX_CHAIN_RE.finditer(span))

    if not matches:
        return None

    return matches[-1]


def _looks_like_org_misc(text: str, start: int, end: int) -> bool:
    # Äußere Leerzeichen vor der Prüfung entfernen.
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        return False

    raw_span = text[start:end]
    suffix_match = _find_last_org_suffix_match(raw_span)

    # Ohne Rechtsträgerzusatz keine ORG-Umklassifizierung.
    if suffix_match is None:
        return False

    # Kandidaten-Span bis einschließlich letztem ORG-Suffix beschneiden.
    suffix_end = suffix_match.end("suffix_chain")
    candidate_raw = raw_span[:suffix_end]

    # Mehrzeilige Kandidaten werden verworfen.
    if "\n" in candidate_raw or "\r" in candidate_raw:
        return False

    new_end = start + suffix_end
    new_start, new_end = _strip_outer_whitespace(text, start, new_end)

    if new_start >= new_end:
        return False

    candidate = text[new_start:new_end]

    # Finale Validierung des beschnittenen ORG-Kandidaten.
    if not is_valid_org_span(candidate):
        return False

    return True


def _looks_like_person_misc(text: str, start: int, end: int) -> bool:
    # Äußere Leerzeichen vor der Prüfung entfernen.
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        return False

    raw_span = text[start:end]

    # Mehrzeilige Kandidaten werden verworfen.
    if "\n" in raw_span or "\r" in raw_span:
        return False

    # Nur Spans mit expliziter Anrede werden als Person akzeptiert.
    if _MISC_PER_TITLE_RE.search(raw_span) is None:
        return False

    return True


def refine_misc_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()

        # Nicht-MISC-Treffer unverändert übernehmen.
        if label != "MISC":
            out.append(h)
            continue

        # MISC bei ORG-Indizien zu ORG umklassifizieren.
        if _looks_like_org_misc(text, h.start, h.ende):
            out.append(
                Treffer(
                    h.start,
                    h.ende,
                    "ORG",
                    h.source,
                    from_regex=h.from_regex,
                    from_ner=h.from_ner,
                )
            )
            continue

        # MISC bei Personenanrede zu PER umklassifizieren.
        if _looks_like_person_misc(text, h.start, h.ende):
            out.append(
                Treffer(
                    h.start,
                    h.ende,
                    "PER",
                    h.source,
                    from_regex=h.from_regex,
                    from_ner=h.from_ner,
                )
            )
            continue

    return out