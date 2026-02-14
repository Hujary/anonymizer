import re
from typing import Iterable, Tuple


def finde_url(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung einfacher URL-Formate.

    Erkannt werden:
      - http://...
      - https://...
      - www....

    Rückgabe:
      (start_index, end_index, "URL")

    Design:
      - Bewusst einfache Heuristik
      - Keine vollständige RFC-URL-Validierung
      - Fokus auf praktikabler Maskierung, nicht auf strenger Syntaxprüfung
    """

    # ------------------------------------------------------------------
    # Pattern-Erklärung:
    #
    # \bhttps?://[^\s<>"']+
    #   - http oder https
    #   - ://
    #   - danach alle Nicht-Whitespace-Zeichen, aber bricht an typischen Quotes/Brackets ab
    #
    # |\bwww\.[^\s<>"']+
    #   - www. als Einstieg
    #   - danach alle Nicht-Whitespace-Zeichen, aber bricht an typischen Quotes/Brackets ab
    #
    # Fix:
    #   - Satzzeichen am Ende (.,;:!?) sowie schließende Klammern/Quotes werden NICHT Teil des Treffers
    #   - Umsetzung zweistufig:
    #       1) breit matchen (damit URL nicht zu früh abbricht)
    #       2) trailing punctuation per trim entfernen (Offsets korrekt anpassen)
    # ------------------------------------------------------------------
    rx = re.compile(
        r"\bhttps?://[^\s<>\"]+|\bwww\.[^\s<>\"]+",
        re.IGNORECASE,
    )

    trailing = ".,;:!?)]}\"'"

    for m in rx.finditer(text):
        s, e = m.start(), m.end()

        while e > s and text[e - 1] in trailing:
            e -= 1

        if e <= s:
            continue

        yield (s, e, "URL")