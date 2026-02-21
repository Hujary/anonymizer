# detectors/regex/finance.py
#
# Regex-basierte Erkennung finanzbezogener Daten:
#   - IBAN (DE)
#   - USt-IdNr (DE)
#   - Geldbeträge (€, EUR, verschiedene Schreibweisen)
#
# Rückgabeformat:
#   (start_index, end_index, label)
#   -> Character-Offsets für Masking-Pipeline

import re
from typing import Iterable, Tuple


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