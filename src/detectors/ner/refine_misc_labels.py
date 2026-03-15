from __future__ import annotations

import re
from typing import List

from core.typen import Treffer

from .postprocess_helpers.org.validate_org_span import is_valid_org_span
from .postprocess_helpers.org.org_blacklists import ORG_LEGAL_SUFFIXES


_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)

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

_MISC_PER_TITLE_RE = re.compile(
    r"(?<![A-Za-zÄÖÜäöüß])(Herr|Herrn|Frau)(?=\s+[A-ZÄÖÜ])",
    re.IGNORECASE,
)


def _strip_outer_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


def _find_last_org_suffix_match(span: str) -> re.Match[str] | None:
    matches = list(_ORG_SUFFIX_CHAIN_RE.finditer(span))

    if not matches:
        return None

    return matches[-1]


def _looks_like_org_misc(text: str, start: int, end: int) -> bool:
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        print("[MISC->ORG] DROP: leer nach outer whitespace")
        return False

    raw_span = text[start:end]
    print(f"[MISC->ORG] CHECK raw_span={raw_span!r} start={start} end={end}")

    suffix_match = _find_last_org_suffix_match(raw_span)

    if suffix_match is None:
        print("[MISC->ORG] DROP: kein ORG-Suffix gefunden")
        return False

    suffix_end = suffix_match.end("suffix_chain")
    candidate_raw = raw_span[:suffix_end]

    if "\n" in candidate_raw or "\r" in candidate_raw:
        print("[MISC->ORG] DROP: Zeilenumbruch innerhalb Kandidat")
        return False

    new_end = start + suffix_end
    new_start, new_end = _strip_outer_whitespace(text, start, new_end)

    if new_start >= new_end:
        print("[MISC->ORG] DROP: leer nach finalem trim")
        return False

    candidate = text[new_start:new_end]
    valid = is_valid_org_span(candidate)
    print(f"[MISC->ORG] VALIDATE candidate={candidate!r} valid={valid}")

    if not valid:
        print("[MISC->ORG] DROP: Validator hat verworfen")
        return False

    print("[MISC->ORG] KEEP: MISC wird zu ORG umklassifiziert")
    return True


def _looks_like_person_misc(text: str, start: int, end: int) -> bool:
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        print("[MISC->PER] DROP: leer nach outer whitespace")
        return False

    raw_span = text[start:end]
    print(f"[MISC->PER] CHECK raw_span={raw_span!r} start={start} end={end}")

    if "\n" in raw_span or "\r" in raw_span:
        print("[MISC->PER] DROP: Zeilenumbruch im Kandidat")
        return False

    if _MISC_PER_TITLE_RE.search(raw_span) is None:
        print("[MISC->PER] DROP: keine Anrede gefunden")
        return False

    print("[MISC->PER] KEEP: MISC wird zu PER umklassifiziert")
    return True


def refine_misc_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    print("\n==================== MISC REFINER ====================")

    for h in hits:
        label = str(h.label).strip().upper()

        if label != "MISC":
            out.append(h)
            continue

        misc_text = text[h.start:h.ende]
        print(
            f"[MISC] INPUT label=MISC start={h.start} end={h.ende} "
            f"text={misc_text!r}"
        )

        if _looks_like_org_misc(text, h.start, h.ende):
            print(
                f"[MISC->ORG] OUTPUT label=ORG start={h.start} end={h.ende} "
                f"text={misc_text!r}"
            )
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

        if _looks_like_person_misc(text, h.start, h.ende):
            print(
                f"[MISC->PER] OUTPUT label=PER start={h.start} end={h.ende} "
                f"text={misc_text!r}"
            )
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

        print("[MISC] OUTPUT verworfen")

    print("======================================================\n")

    return out