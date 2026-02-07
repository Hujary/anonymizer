import re
from typing import Iterable, Tuple

def finde_location(text: str) -> Iterable[Tuple[int, int, str]]:
    for m in re.finditer(r"\b\d{5}\b", text):
        yield (m.start(), m.end(), "PLZ")

    plz_ort = re.compile(
        r"\b\d{5}\s+(?P<city>[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)*)\b"
    )
    for m in plz_ort.finditer(text):
        yield (m.start("city"), m.end("city"), "ORT")

    # Echte Straßentypen
    strassen_suffix = (
        r"(?:straße|str\.|weg|allee|platz|ring|gasse|ufer|damm|hof|steig|kai|chaussee|promenade|brücke)"
    )

    # Variante A: "<Name><Suffix> <Hausnummer>"
    muster_a = re.compile(
        rf"""
        (?<![A-Za-z0-9._%+\-])                # nicht innerhalb von E-Mail/Usernamen starten
        [A-ZÄÖÜ][a-zäöüß\-]+
        (?:\s+[A-ZÄÖÜa-zäöüß\-]+)*            # weitere Bestandteile des Straßennamens
        \s+{strassen_suffix}
        \s+\d+[a-zA-Z]?                       # Hausnummer
        (?!@[A-Za-z0-9.\-])                   # nicht direkt vor @ stehen (keine Teile von E-Mails)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # Variante B: "Am|Im|An ... <Hausnummer>" (nur mit Hausnummer!)
    muster_b = re.compile(
        r"""
        (?<![A-Za-z0-9._%+\-])
        (?:Am|An|Im|In|Auf|Zu|Zur|Zum)\s+
        [A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)*
        \s+\d+[a-zA-Z]?
        (?!@[A-Za-z0-9.\-])
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # Kontext-Filter: Zeilen mit E-Mail-Adressen überspringen
    def skip_in_email_context(start: int, end: int) -> bool:
        segment = text[max(0, start - 40): min(len(text), end + 40)]
        return "@" in segment

    for rx in (muster_a, muster_b):
        for m in rx.finditer(text):
            s, e = m.start(), m.end()
            if not skip_in_email_context(s, e):
                yield (s, e, "STRASSE")