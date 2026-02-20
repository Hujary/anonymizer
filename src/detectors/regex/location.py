from __future__ import annotations

import re
from typing import Iterable, Tuple

_PLZ_RE = re.compile(
    r"(?<!\d)(?:D[-\s])?(?P<plz>\d{5})(?!\d)",
    re.IGNORECASE,
)


def finde_location(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung von PLZ (DE-fokussiert), robust gegen False Positives
    wie Ticket-IDs (z.B. ST-2024-00123).

    Erkannt wird:
      - 5-stellige PLZ
      - optional mit Prefix "D-" oder "D " (z.B. D-70173)

    Rückgabeformat:
      (start_index, end_index, "PLZ")
    """

    allowed_left = set(" \t\r\n,;:([{\"'")   # typische Trenner vor PLZ
    allowed_right = set(" \t\r\n,;:.)]}/\"'")  # typische Trenner nach PLZ

    for m in _PLZ_RE.finditer(text):
        s, e = m.start("plz"), m.end("plz")

        prev = text[s - 1] if s > 0 else ""
        nxt = text[e] if e < len(text) else ""

        if prev and prev not in allowed_left:
            continue
        if nxt and nxt not in allowed_right:
            continue

        # Extra-Heuristik: wenn direkt davor ein Bindestrich/Underscore/Slash steht,
        # ist es fast immer eine ID (Ticket, Version, etc.) -> nicht als PLZ zählen.
        # Das greift auch dann, wenn vorher whitespace ist nicht der Fall.
        if s > 0 and text[s - 1] in "-_/":
            continue

        yield (s, e, "PLZ")