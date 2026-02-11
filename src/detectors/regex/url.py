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
    # \bhttps?://[^\s]+
    #   - http oder https
    #   - ://
    #   - danach alle Nicht-Whitespace-Zeichen
    #
    # |\bwww\.[^\s]+\b
    #   - www. als Einstieg
    #   - danach alle Nicht-Whitespace-Zeichen
    #   - endet an Wortgrenze
    #
    # Einschränkungen:
    #   - Keine Validierung von TLDs
    #   - Klammern oder Satzzeichen am Ende können Teil des Matches werden
    #   - Keine Unterstützung für FTP, Mailto etc.
    # ------------------------------------------------------------------
    rx = re.compile(
        r"\bhttps?://[^\s]+|\bwww\.[^\s]+\b",
        re.IGNORECASE
    )

    for m in rx.finditer(text):
        yield (m.start(), m.end(), "URL")