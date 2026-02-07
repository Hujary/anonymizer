import re
from typing import Iterable, Tuple

def finde_contact(text: str) -> Iterable[Tuple[int, int, str]]:
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.MULTILINE)

    # Internationale DE-Nummern (+49/0049): Trennzeichen erlaubt, auch '-'
    intl = re.compile(
        r"(?<!\w)(?:\+|00)49[\s()/\-]*\(?(?:0)?\)?[\s()/\-]*\d{1,5}(?:[\s()/\-]*\d{2,}){1,4}(?!\w)",
        re.MULTILINE,
    )

    # Nationale DE-Nummern (0…): NACH der Vorwahl NUR Space, Slash oder ') ' – KEIN reines '-'
    # Beispiel: 089 1234567, (089) 1234567, 0151/2345678
    domestic = re.compile(
        r"(?<!\w)0\d{2,5}(?:\)\s+|[ )/]\s*)\d{2,}(?:[ )/]\d{2,}){0,4}(?!\w)",
        re.MULTILINE,
    )

    def is_false_positive_phone(s: str, start: int) -> bool:
        # 1) zu wenige Ziffern
        digits = re.sub(r"\D", "", s)
        if len(digits) < 7:
            return True
        # 2) typische Rechnungs-/Ticketnummer im Umfeld: AA-YYYY-####
        #    Prüfe 10 Zeichen vor dem Match auf Muster wie "TS-2024-0915"
        prefix = text[max(0, start - 12):start]
        if re.search(r"[A-ZÄÖÜ]{2,5}-\d{4}\s*-\s*\d{2,}", prefix):
            return True
        return False

    for m in email.finditer(text):
        yield (m.start(), m.end(), "E_MAIL")

    # erst internationale Formen
    for m in intl.finditer(text):
        s, e = m.start(), m.end()
        val = text[s:e]
        if not is_false_positive_phone(val, s):
            yield (s, e, "TELEFON")

    # dann nationale Formen
    for m in domestic.finditer(text):
        s, e = m.start(), m.end()
        val = text[s:e]
        if not is_false_positive_phone(val, s):
            yield (s, e, "TELEFON")