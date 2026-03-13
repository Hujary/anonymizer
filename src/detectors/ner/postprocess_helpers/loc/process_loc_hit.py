from __future__ import annotations

import re

from core.typen import Treffer

from .extract_street_span import extract_street_span_from_loc
from .normalize_loc_span import normalize_loc_span
from .validate_loc_span import is_plausible_loc_span
from .loc_blacklists import TECHNICAL_LOC_BLACKLIST


print("DEBUG: LOADED src/detectors/ner/postprocess_helpers/loc/process_loc_hit.py")


_LOC_TOKEN_SPLIT_RE = re.compile(r"[\s\-_\/]+")


def _normalize_blacklist_token(token: str) -> str:
    strip_chars = ",.;:(){}[]\"'`„“‚‘-–—"
    return token.strip().lower().strip(strip_chars)


def _contains_technical_loc_term(span: str) -> bool:
    raw_parts = _LOC_TOKEN_SPLIT_RE.split(span)

    print(f"LOC CHECK | span={span!r}")
    print(f"LOC CHECK | raw_parts={raw_parts!r}")

    for raw in raw_parts:
        token = _normalize_blacklist_token(raw)
        print(f"LOC CHECK | raw={raw!r} -> token={token!r}")

        if not token:
            continue

        if token in TECHNICAL_LOC_BLACKLIST:
            print(f"LOC CHECK | blacklist_match={token!r}")
            return True

    print("LOC CHECK | no_blacklist_match")
    return False


def process_loc_hit(text: str, hit: Treffer) -> Treffer | None:
    input_span = text[hit.start:hit.ende]
    print(
        f"PROCESS_LOC | input "
        f"start={hit.start:<4} "
        f"ende={hit.ende:<4} "
        f"text={input_span!r}"
    )

    street_span = extract_street_span_from_loc(text, hit.start, hit.ende)

    if street_span is not None:
        start, end = street_span
        street_text = text[start:end]

        print(
            f"PROCESS_LOC | street_span_found "
            f"start={start:<4} "
            f"ende={end:<4} "
            f"text={street_text!r}"
        )

        return Treffer(
            start,
            end,
            "LOC",
            hit.source,
            from_regex=hit.from_regex,
            from_ner=hit.from_ner,
        )

    normalized_loc = normalize_loc_span(text, hit)

    if normalized_loc is None:
        print("PROCESS_LOC | normalize_loc_span returned None")
        return None

    span = text[normalized_loc.start:normalized_loc.ende].strip()

    print(
        f"PROCESS_LOC | normalized "
        f"start={normalized_loc.start:<4} "
        f"ende={normalized_loc.ende:<4} "
        f"text={span!r}"
    )

    if not span:
        print("PROCESS_LOC | empty normalized span")
        return None

    if _contains_technical_loc_term(span):
        print("PROCESS_LOC | rejected by technical blacklist")
        return None

    plausible = is_plausible_loc_span(span)
    print(f"PROCESS_LOC | plausible={plausible!r}")

    if not plausible:
        print("PROCESS_LOC | rejected by plausibility check")
        return None

    print("PROCESS_LOC | accepted")
    return normalized_loc