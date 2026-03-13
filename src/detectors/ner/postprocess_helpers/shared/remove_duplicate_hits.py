from __future__ import annotations

from typing import List

from core.typen import Treffer


def remove_duplicate_hits(hits: List[Treffer]) -> List[Treffer]:
    seen: set[tuple[int, int, str]] = set()
    result: List[Treffer] = []

    for hit in hits:
        key = (hit.start, hit.ende, hit.label)
        if key in seen:
            continue
        seen.add(key)
        result.append(hit)

    return result