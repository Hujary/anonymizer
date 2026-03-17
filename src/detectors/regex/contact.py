import re
from typing import Iterable, Tuple


def finde_contact(text: str) -> Iterable[Tuple[int, int, str]]:
    email = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        re.MULTILINE,
    )

    intl = re.compile(
        r"(?<!\w)(?:\+|00)49[\s()/\-]*\(?(?:0)?\)?[\s()/\-]*\d{1,5}(?:[\s()/\-]*\d{2,}){1,4}(?:-\d{1,4})?(?!\w)",
        re.MULTILINE,
    )

    domestic = re.compile(
        r"(?<!\w)0\d{2,5}(?:\)\s+|[ )/]\s*)\d{2,}(?:[ )/]\d{2,}){0,4}(?:-\d{1,4})?(?!\w)",
        re.MULTILINE,
    )

    def is_false_positive_phone(s: str, start: int) -> bool:
        digits = re.sub(r"\D", "", s)
        if len(digits) < 7:
            return True

        prefix = text[max(0, start - 12):start]
        if re.search(r"[A-ZÄÖÜ]{2,5}-\d{4}\s*-\s*\d{2,}", prefix):
            return True

        return False

    for m in email.finditer(text):
        yield (m.start(), m.end(), "E_MAIL")

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