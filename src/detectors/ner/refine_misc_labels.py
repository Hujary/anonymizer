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


def _looks_like_org_misc(text: str, start: int, end: int) -> tuple[bool, int, int]:
    start, end = _strip_outer_whitespace(text, start, end)

    if start >= end:
        print("[MISC->ORG] DROP: leer nach outer whitespace")
        return False, start, end

    raw_span = text[start:end]
    print(f"[MISC->ORG] CHECK raw_span={raw_span!r} start={start} end={end}")

    suffix_match = _find_last_org_suffix_match(raw_span)

    if suffix_match is None:
        print("[MISC->ORG] DROP: kein ORG-Suffix gefunden")
        return False, start, end

    suffix_text = suffix_match.group("suffix_chain")
    suffix_start = suffix_match.start("suffix_chain")
    suffix_end = suffix_match.end("suffix_chain")

    print(
        f"[MISC->ORG] SUFFIX gefunden: suffix={suffix_text!r} "
        f"suffix_start={suffix_start} suffix_end={suffix_end}"
    )

    candidate_raw = raw_span[:suffix_end]
    print(f"[MISC->ORG] CANDIDATE raw bis suffix={candidate_raw!r}")

    if "\n" in candidate_raw or "\r" in candidate_raw:
        print("[MISC->ORG] DROP: Zeilenumbruch innerhalb Kandidat")
        return False, start, end

    new_end = start + suffix_end
    new_start, new_end = _strip_outer_whitespace(text, start, new_end)

    if new_start >= new_end:
        print("[MISC->ORG] DROP: leer nach finalem trim")
        return False, new_start, new_end

    candidate = text[new_start:new_end]
    print(
        f"[MISC->ORG] FINAL candidate={candidate!r} "
        f"new_start={new_start} new_end={new_end}"
    )

    valid = is_valid_org_span(candidate)
    print(f"[MISC->ORG] VALIDATE candidate={candidate!r} valid={valid}")

    if not valid:
        print("[MISC->ORG] DROP: Validator hat verworfen")
        return False, new_start, new_end

    print("[MISC->ORG] KEEP: MISC wird zu ORG umklassifiziert")
    return True, new_start, new_end


def refine_misc_labels(text: str, hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []

    print("\n==================== MISC -> ORG REFINER ====================")

    for h in hits:
        label = str(h.label).strip().upper()

        if label != "MISC":
            out.append(h)
            continue

        misc_text = text[h.start:h.ende]
        print(
            f"[MISC->ORG] INPUT label=MISC start={h.start} end={h.ende} "
            f"text={misc_text!r}"
        )

        is_org, new_start, new_end = _looks_like_org_misc(text, h.start, h.ende)

        if is_org:
            converted_text = text[new_start:new_end]
            print(
                f"[MISC->ORG] OUTPUT label=ORG start={new_start} end={new_end} "
                f"text={converted_text!r}"
            )

            out.append(
                Treffer(
                    new_start,
                    new_end,
                    "ORG",
                    h.source,
                    from_regex=h.from_regex,
                    from_ner=h.from_ner,
                )
            )
        else:
            print("[MISC->ORG] OUTPUT verworfen")

    print("=============================================================\n")

    return out