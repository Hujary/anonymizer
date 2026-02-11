import re
from typing import Iterable, Tuple


def finde_invoice(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung typischer Rechnungsnummern-Formate.

    Rückgabe:
        (start_index, end_index, "RECHNUNGS_NUMMER")

    Design:
        - Mehrere Pattern-Kategorien (A–D)
        - Kategorie A maskiert nur die eigentliche ID (nicht das Schlüsselwort)
        - Kategorien B–D maskieren das komplette Match
    """

    patterns: list[re.Pattern] = [
        # ------------------------------------------------------------------
        # A) Schlüsselwort + ID rechts davon
        #
        # Ziel:
        #   Nur die eigentliche ID maskieren, nicht das Wort "Rechnung".
        #
        # Beispiele:
        #   "Rechnungsnummer: TS-2024-0915"
        #   "Rg.-Nr. 2024-00127"
        #   "Invoice No. INV-230045"
        #
        # Einschränkung:
        #   - Sehr generisch → kann False Positives erzeugen
        #   - ID-Muster erlaubt relativ breite Zeichenmenge
        # ------------------------------------------------------------------
        re.compile(
            r"""(?ix)
            \b(?:rechnung(?:s)?(?:nr\.?|nummer)?|rg\.?\-?nr\.?|re\.?\-?nr\.?|invoice(?:\s*no\.?)?)
            \s*[:#]?\s*
            (?P<ID>[A-Z0-9][A-Z0-9\-\/]{3,24})
            """,
        ),

        # ------------------------------------------------------------------
        # B) Vendor-Style: PREFIX-YYYY-NNNN
        #
        # Beispiele:
        #   TS-2024-0915
        #
        # Annahmen:
        #   - Jahr beginnt mit 20xx
        #   - 3–6 Ziffern laufende Nummer
        #
        # Risiko:
        #   - Kann auch andere Codes matchen, die kein Invoice sind
        # ------------------------------------------------------------------
        re.compile(r"\b[A-Z]{2,6}-20\d{2}-\d{3,6}\b"),

        # ------------------------------------------------------------------
        # C) Jahr + laufende Nummer
        #
        # Beispiele:
        #   2024-00127
        #   2024/1234
        #
        # Mindestlänge 3 Ziffern, um typische Datumsformate (2024-01-01)
        # nicht zu erfassen.
        #
        # Restrisiko:
        #   - Kann Projektnummern oder andere IDs matchen
        # ------------------------------------------------------------------
        re.compile(r"\b20\d{2}[-/]\d{3,6}\b"),

        # ------------------------------------------------------------------
        # D) Kurze Präfixe mit laufender Nummer
        #
        # Beispiele:
        #   INV-230045
        #   RE123456
        #   RG_004512
        #
        # Case-insensitive
        #
        # Risiko:
        #   - Sehr generisch → kann andere ID-Formate erfassen
        # ------------------------------------------------------------------
        re.compile(r"\b(?:INV|RE|RG|RN|RNG|BILL)[-_]?\d{4,8}\b", re.IGNORECASE),
    ]

    # ----------------------------------------------------------------------
    # Kategorie A:
    #   Nur die benannte Gruppe "ID" wird maskiert.
    #   Das Schlüsselwort selbst bleibt im Text erhalten.
    # ----------------------------------------------------------------------
    for m in patterns[0].finditer(text):
        s, e = m.start("ID"), m.end("ID")
        yield (s, e, "RECHNUNGS_NUMMER")

    # ----------------------------------------------------------------------
    # Kategorien B–D:
    #   Komplettes Match wird maskiert.
    #
    # Hinweis:
    #   Keine Overlap-Resolution hier – das ist Aufgabe der Masking-Pipeline.
    # ----------------------------------------------------------------------
    for p in patterns[1:]:
        for m in p.finditer(text):
            yield (m.start(), m.end(), "RECHNUNGS_NUMMER")