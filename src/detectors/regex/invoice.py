import re
from typing import Iterable, Tuple

def finde_invoice(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Erkennung häufiger Rechnungsnummer-Formate.
    Liefert (start, ende, "RECHNUNGS_NUMMER").
    """

    patterns: list[re.Pattern] = [
        # A) Klassisch deutsch mit Schlüsselwort + ID rechts davon
        #    Beispiele: "Rechnungsnummer: TS-2024-0915", "Rg.-Nr. 2024-00127", "Invoice No. INV-230045"
        re.compile(
            r"""(?ix)
            \b(?:rechnung(?:s)?(?:nr\.?|nummer)?|rg\.?\-?nr\.?|re\.?\-?nr\.?|invoice(?:\s*no\.?)?)
            \s*[:#]?\s*
            (?P<ID>[A-Z0-9][A-Z0-9\-\/]{3,24})
            """,
        ),

        # B) Vendor-Style: PREFIX-YYYY-NNNN  (z. B. TS-2024-0915)
        re.compile(r"\b[A-Z]{2,6}-20\d{2}-\d{3,6}\b"),

        # C) Jahr + laufende Nr. (mind. 3-stellig, damit kein Datum): 2024-00127 oder 2024/1234
        re.compile(r"\b20\d{2}[-/]\d{3,6}\b"),

        # D) Kurze Präfixe mit laufender Nr.: INV-230045, RE123456, RG_004512
        re.compile(r"\b(?:INV|RE|RG|RN|RNG|BILL)[-_]?\d{4,8}\b", re.IGNORECASE),
    ]

    # A: Schlüsselwort-Pattern mit Gruppe -> nur die ID maskieren
    for m in patterns[0].finditer(text):
        s, e = m.start("ID"), m.end("ID")
        yield (s, e, "RECHNUNGS_NUMMER")

    # B–D: komplette Matches
    for p in patterns[1:]:
        for m in p.finditer(text):
            yield (m.start(), m.end(), "RECHNUNGS_NUMMER")