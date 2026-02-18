# detectors/regex/finance.py
#
# Regex-basierte Erkennung finanzbezogener Daten:
#   - IBAN (DE)
#   - BIC (optional via Config)
#   - USt-IdNr (DE)
#   - Geldbeträge (€, EUR, verschiedene Schreibweisen)
#
# Rückgabeformat:
#   (start_index, end_index, label)
#   -> Character-Offsets für Masking-Pipeline

import re
from typing import Iterable, Tuple
from core.einstellungen import MASK_BIC  # Feature-Flag für BIC-Erkennung


def finde_finance(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Durchsucht Text nach finanzbezogenen Mustern.
    Liefert Character-Spans + semantisches Label.
    """

    # ------------------------------------------------------------------
    # IBAN (Deutschland)
    # Format: DE + 20 Ziffern (insgesamt 22 Zeichen)
    # Beispiel: DE89370400440532013000
    # ------------------------------------------------------------------
    for m in re.finditer(r"(?<!\w)DE(?:[ \t]*\d){20}(?!\w)", text):
        yield (m.start(), m.end(), "IBAN")

    # ------------------------------------------------------------------
    # BIC (optional, konfigurierbar)
    # 8 oder 11 Zeichen:
    #   4 Bankcode (A-Z)
    #   2 Ländercode (A-Z)
    #   2-5 alphanumerische Zeichen
    # ------------------------------------------------------------------
    if MASK_BIC:
        for m in re.finditer(
            r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?\b",
            text
        ):
            yield (m.start(), m.end(), "BIC")

    # ------------------------------------------------------------------
    # USt-IdNr (Deutschland)
    # Format: DE + 9 Ziffern
    # Beispiel: DE123456789
    # ------------------------------------------------------------------
    for m in re.finditer(r"\bDE\d{9}\b", text):
        yield (m.start(), m.end(), "USTID")

    # ------------------------------------------------------------------
    # Geldbeträge
    #
    # Unterstützt:
    #   - € 1.234,56
    #   - EUR 1234.56
    #   - 1.234,56 €
    #   - 1234 EUR
    #   - optional + / -
    #   - Tausendertrennzeichen (Punkt oder Leerzeichen)
    #
    # Einschränkung:
    #   - Keine Währungsvalidierung
    #   - Keine Kontextprüfung (z.B. Prozent vs Betrag)
    # ------------------------------------------------------------------
    geld_pattern = r"""
        (?:
            (?:€|EUR)\s*[+\-]?(?:\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,]\d{2})?
            |
            [+\-]?(?:\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,]\d{2})?\s*(?:€|EUR)
        )
    """

    for m in re.finditer(geld_pattern, text, re.VERBOSE | re.IGNORECASE):
        yield (m.start(), m.end(), "BETRAG")