import re
from typing import Iterable, Tuple


def finde_contact(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung von Kontaktdaten.

    Erkannt werden:
      - E-Mail-Adressen
      - Deutsche Telefonnummern (international +49/0049 und national 0...)

    Rückgabe:
      (start_index, end_index, label)
      Labels:
        - "E_MAIL"
        - "TELEFON"

    Designentscheidungen:
      - Telefon wird in zwei Stufen gesucht: erst international, dann national
      - Heuristik-Filter reduziert False Positives (zu kurze Nummern, Invoice/Ticket-Umfeld)
      - Word-Boundary-ähnliche Lookarounds verhindern Matches mitten in Wörtern/IDs
    """

    # ------------------------------------------------------------------
    # E-Mail:
    #   - klassisches Muster: local@domain.tld
    #   - MULTILINE ist hier praktisch irrelevant, stört aber nicht
    #
    # Einschränkung:
    #   - Kein RFC-5322 Vollumfang
    #   - Internationalisierte Domains/Localparts nur eingeschränkt
    # ------------------------------------------------------------------
    email = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        re.MULTILINE,
    )

    # ------------------------------------------------------------------
    # Telefon (international, Deutschland):
    #   - beginnt mit +49 oder 0049
    #   - erlaubt Trennzeichen: Space, (), /, -
    #   - optional "(0)" oder "0" nach +49 (wie oft in Schreibweise +49 (0) 30 ...)
    #
    # Ziel:
    #   - robuste Erkennung realer Schreibvarianten
    #
    # Risiko:
    #   - kann numerische Sequenzen matchen, wenn Umgebung passt
    # ------------------------------------------------------------------
    intl = re.compile(
        r"(?<!\w)(?:\+|00)49[\s()/\-]*\(?(?:0)?\)?[\s()/\-]*\d{1,5}(?:[\s()/\-]*\d{2,}){1,4}(?!\w)",
        re.MULTILINE,
    )

    # ------------------------------------------------------------------
    # Telefon (national, Deutschland):
    #   - beginnt mit 0 + 2..5 Ziffern Vorwahl
    #   - danach: Separator muss Space, Slash oder ') ' sein
    #   - explizit KEIN reines '-' direkt nach der Vorwahl, um Matches wie "2024-00127"
    #     (Rechnungsnummern) weniger wahrscheinlich zu machen
    #
    # Beispiele:
    #   089 1234567
    #   (089) 1234567
    #   0151/2345678
    #
    # Risiko:
    #   - bleibt Heuristik, kann immer noch mit IDs kollidieren
    # ------------------------------------------------------------------
    domestic = re.compile(
        r"(?<!\w)0\d{2,5}(?:\)\s+|[ )/]\s*)\d{2,}(?:[ )/]\d{2,}){0,4}(?!\w)",
        re.MULTILINE,
    )

    # ------------------------------------------------------------------
    # False-Positive-Filter für Telefon:
    #
    # 1) Minimale Ziffernanzahl:
    #    - entfernt kurze Matches (z.B. "0123 45")
    #
    # 2) Kontextprüfung auf typische Rechnungs-/Ticketformate:
    #    - Muster AA-YYYY-#### in den Zeichen direkt davor
    #    - reduziert Kollisionen mit Vendor-IDs, die sonst im Phone-Regex landen
    #
    # Schwächen:
    #   - Kontextfenster ist klein und heuristisch
    #   - kann echte Telefonnummern fälschlich verwerfen, wenn direkt davor so ein Pattern steht
    # ------------------------------------------------------------------
    def is_false_positive_phone(s: str, start: int) -> bool:
        digits = re.sub(r"\D", "", s)
        if len(digits) < 7:
            return True

        prefix = text[max(0, start - 12):start]
        if re.search(r"[A-ZÄÖÜ]{2,5}-\d{4}\s*-\s*\d{2,}", prefix):
            return True

        return False

    # ------------------------------------------------------------------
    # E-Mails liefern
    # ------------------------------------------------------------------
    for m in email.finditer(text):
        yield (m.start(), m.end(), "E_MAIL")

    # ------------------------------------------------------------------
    # Telefonnummern:
    #   Reihenfolge ist absichtlich:
    #     1) international (+49/0049) -> spezifischer
    #     2) national (0...)         -> breiter / anfälliger
    #
    # Overlap-Auflösung (z.B. wenn Regex sich überlappt) macht downstream die Masking-Engine.
    # ------------------------------------------------------------------
    for m in intl.finditer(text):
        s, e = m.start(), m.end()
        val = text[s:e]
        if not is_false_positive_phone(val, s):
            yield (s, e, "TELEFON")

    for m in domestic.finditer(text):
        s, e = m.start(), m.end()
        val = text[s:e]
        if not is_false_positive_phone(val, s):
            yield (s, e, "TELEFON")