# detectors/regex/finance.py
import re
from typing import Iterable, Tuple
from core.einstellungen import MASK_BIC

def finde_finance(text: str) -> Iterable[Tuple[int, int, str]]:
    for m in re.finditer(r"\bDE\d{20}\b", text):
        yield (m.start(), m.end(), "IBAN")

    if MASK_BIC:
        for m in re.finditer(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?\b", text):
            yield (m.start(), m.end(), "BIC")

    for m in re.finditer(r"\bDE\d{9}\b", text):
        yield (m.start(), m.end(), "USTID")

    geld_pattern = r"""
        (?:
            (?:€|EUR)\s*[+\-]?(?:\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,]\d{2})?
            |
            [+\-]?(?:\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,]\d{2})?\s*(?:€|EUR)
        )
    """
    for m in re.finditer(geld_pattern, text, re.VERBOSE | re.IGNORECASE):
        yield (m.start(), m.end(), "BETRAG")