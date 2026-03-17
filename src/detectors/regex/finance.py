import re
from typing import Iterable, Tuple


def finde_finance(text: str) -> Iterable[Tuple[int, int, str]]:
    for m in re.finditer(r"(?<!\w)DE(?:[ \t]*\d){20}(?!\w)", text):
        yield (m.start(), m.end(), "IBAN")