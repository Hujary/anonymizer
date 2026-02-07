from __future__ import annotations

from typing import List

from core.typen import Treffer
from services.manual_tokens import as_match_list, ManualToken


def finde_manual_tokens(text: str) -> List[Treffer]:
    hits: List[Treffer] = []
    if not text:
        return hits

    tokens = as_match_list()
    if not tokens:
        return hits

    for entry in tokens:
        value = entry.value
        if not value:
            continue
        typ = entry.typ.upper()
        start = 0
        while True:
            idx = text.find(value, start)
            if idx == -1:
                break
            end = idx + len(value)
            hits.append(Treffer(idx, end, typ, "dict"))
            start = end

    return hits