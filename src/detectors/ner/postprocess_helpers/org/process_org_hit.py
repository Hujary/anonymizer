from __future__ import annotations

from core.typen import Treffer


def process_org_hit(text: str, hit: Treffer) -> Treffer | None:
    span = text[hit.start:hit.ende].strip()

    if not span:
        return None

    return Treffer(
        hit.start,
        hit.ende,
        "ORG",
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )