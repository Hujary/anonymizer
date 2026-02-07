import re
from typing import Iterable, Tuple

def finde_date(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Erkennt:
      - ISO: 2024-12-01
      - Deutsch: 17. Oktober 2024
      - Englisch: March 12, 2025 / 12 March 2025 / Dec 5, 2023
    """
    monate = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mär(?:z)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Okt(?:ober)?|Oct(?:ober)?|Nov(?:ember)?|Dez(?:ember)?|Dec(?:ember)?)"
    )

    patterns = [
        # ISO 2024-12-01
        re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),

        # Deutsch numerisch: 17.10.2024
        re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"),

        # Deutsch lang: 17. Oktober 2024
        re.compile(rf"\b\d{{1,2}}\.\s*{monate}\s*\d{{4}}\b", re.IGNORECASE),

        # Englisch: March 12, 2025  / Dec 5, 2023
        re.compile(rf"\b{monate}\s+\d{{1,2}},\s*\d{{4}}\b", re.IGNORECASE),

        # Englisch (invertiert): 12 March 2025
        re.compile(rf"\b\d{{1,2}}\s+{monate}\s+\d{{4}}\b", re.IGNORECASE),
    ]

    for rx in patterns:
        for m in rx.finditer(text):
            yield (m.start(), m.end(), "DATUM")