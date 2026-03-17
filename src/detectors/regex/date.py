import re
from typing import Iterable, Tuple


def finde_date(text: str) -> Iterable[Tuple[int, int, str]]:
    monate = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mär(?:z)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Okt(?:ober)?|Oct(?:ober)?|Nov(?:ember)?|Dez(?:ember)?|Dec(?:ember)?)"
    )

    patterns = [
        re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),

        re.compile(
            r"""
            \b
            (?:0?[1-9]|[12]\d|3[01])      # Tag 1-31
            [./-]
            (?:0?[1-9]|1[0-2])            # Monat 1-12
            [./-]
            \d{2,4}                       # Jahr (2-4 stellig)
            \b
            """,
            re.VERBOSE,
        ),

        re.compile(
            r"""
            (?<!\d\.)                      # nicht Teil von x.<hier>  (blockt v2.8.1 am "8.1")
            \b
            (?:0?[1-9]|[12]\d|3[01])       # Tag 1-31
            \.
            (?:0?[1-9]|1[0-2])             # Monat 1-12
            \b
            (?!\.\d)                       # nicht Teil von <hier>.x (blockt 8.1.3)
            """,
            re.VERBOSE,
        ),

        re.compile(
            r"""
            \b
            (?:0?[1-9]|1[0-2])        # Monat 1-12
            [./-]
            (?:19|20)\d{2}            # Jahr 1900–2099
            \b
            """,
            re.VERBOSE,
        ),

        re.compile(rf"\b\d{{1,2}}\.\s*{monate}\s*\d{{4}}\b", re.IGNORECASE),
        re.compile(rf"\b\d{{1,2}}\.\s*{monate}\b", re.IGNORECASE),
        re.compile(rf"\b{monate}\s+\d{{1,2}},\s*\d{{4}}\b", re.IGNORECASE),
        re.compile(rf"\b\d{{1,2}}\s+{monate}\s+\d{{4}}\b", re.IGNORECASE),
    ]

    for rx in patterns:
        for m in rx.finditer(text):
            yield (m.start(), m.end(), "DATUM")