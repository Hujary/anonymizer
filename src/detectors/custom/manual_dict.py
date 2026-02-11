###     Manuelle Dictionary-Detektion (Substring-basiert)
### __________________________________________________________________________
#
#  - Nutzt persistente, benutzerdefinierte Tokens (z.B. Namen, Projektnummern)
#  - Keine Regex, sondern einfache Substring-Suche via str.find
#  - Case-sensitiv (keine Normalisierung)
#  - Keine Overlap-Resolution (wird später in der Masking-Pipeline behandelt)
#  - Quelle wird als "dict" markiert


from __future__ import annotations

from typing import List

# Gemeinsame Treffer-Datenstruktur (Start, Ende, Label, Quelle)
from core.typen import Treffer

# Zugriff auf persistente manuelle Tokens
from services.manual_tokens import as_match_list, ManualToken



# Führt eine einfache Substring-Suche für alle manuell definierten Tokens aus.
def finde_manual_tokens(text: str) -> List[Treffer]:

    # Sammelliste für alle gefundenen Treffer
    hits: List[Treffer] = []

    # Leerer Input → keine Treffer
    if not text:
        return hits

    # Aktuelle Token-Liste laden (persistenter Speicher)
    tokens = as_match_list()

    # Keine konfigurierten Tokens → nichts zu tun
    if not tokens:
        return hits

    # Iteration über alle gespeicherten Tokens
    for entry in tokens:

        value = entry.value  # Konkreter Suchstring
        if not value:
            continue  # Leere Werte ignorieren

        typ = entry.typ.upper()  # Label vereinheitlichen (z.B. PER, ORG, CUSTOM)

        start = 0  # Startoffset für wiederholte Suche

        # Iterative Suche nach allen Vorkommen des Tokens im Text
        while True:
            idx = text.find(value, start)

            if idx == -1:
                break  # Keine weiteren Treffer

            end = idx + len(value)

            # Treffer erzeugen:
            # - Startindex
            # - Endindex
            # - Label
            # - Quelle = "dict"
            hits.append(Treffer(idx, end, typ, "dict"))

            # Weitersuchen hinter dem aktuellen Treffer
            # → verhindert Overlaps desselben Tokens
            start = end

    return hits