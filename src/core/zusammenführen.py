from __future__ import annotations

from typing import List

from core.typen import Treffer


def _priority(hit: Treffer) -> tuple[int, int, int]:
    source = getattr(hit, "source", "")
    source_rank = 0 if source == "regex" else 1 if source == "ner" else 2
    length_rank = -(hit.ende - hit.start)
    start_rank = hit.start
    return (source_rank, length_rank, start_rank)


def _choose_better(a: Treffer, b: Treffer) -> Treffer:
    return a if _priority(a) <= _priority(b) else b


def zusammenführen(regex_hits: List[Treffer], ner_hits: List[Treffer]) -> List[Treffer]:
    candidates: List[Treffer] = list(regex_hits) + list(ner_hits)

    if not candidates:
        return []

    candidates.sort(key=lambda t: (t.start, t.ende, _priority(t)))

    merged: List[Treffer] = []

    for hit in candidates:
        if not merged:
            merged.append(hit)
            continue

        last = merged[-1]

        if not last.überschneidet(hit):
            merged.append(hit)
            continue

        best = _choose_better(last, hit)
        merged[-1] = best

    return merged