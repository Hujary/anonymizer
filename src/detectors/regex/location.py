from __future__ import annotations

import re
from typing import Iterable, Tuple

_PLZ_RE = re.compile(r"\b\d{5}\b")


def finde_location(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung von PLZ (DE-fokussiert).

    Erkannt wird:
      - PLZ: exakt 5-stellig als eigenständiges Wort

    Rückgabeformat:
      (start_index, end_index, label)
    """

    for m in _PLZ_RE.finditer(text):
        s, e = m.start(), m.end()

        prev = text[s - 1] if s > 0 else ""
        nxt = text[e] if e < len(text) else ""

        if prev.isdigit():
            continue
        if nxt.isdigit():
            continue

        yield (s, e, "PLZ")