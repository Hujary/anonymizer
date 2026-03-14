from __future__ import annotations

import re

from .org_blacklists import ORG_LEGAL_SUFFIXES


# -------------------------------------------------------------
# Bekannte Organisationssuffixe.
# Längere Varianten zuerst, damit z. B. "KGaA" vor "AG" geprüft wird.
# -------------------------------------------------------------
_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)


# -------------------------------------------------------------
# Plausible Zeichen innerhalb eines Organisationsnamens zwischen
# ursprünglichem NER-Treffer und einem späteren Suffix.
#
# Beispiele, die erlaubt sein sollen:
#   " IT-Systeme GmbH"
#   " Logistik GmbH"
#   " & Reuter Logistik GmbH"
#   " Manufacturing GmbH"
#   " Industrie AG"
#   " GmbH & Co KG"
#
# Nicht erlaubt:
#   Zeilenumbrüche
#   offensichtliches Satzende vor dem Suffix
# -------------------------------------------------------------
_ALLOWED_INTERMEDIATE_RE = re.compile(
    r"^[A-Za-zÄÖÜäöüß0-9&\-\/\.\(\) ]*$"
)


# -------------------------------------------------------------
# Sucht rechts vom aktuellen Treffer das nächste legale ORG-Suffix.
# Dabei wird NUR der Bereich bis zum Suffix betrachtet.
#
# Boundary:
# Nach dem Suffix darf kein Buchstabe mehr folgen.
# Punkt/Komma etc. dürfen folgen, gehören aber nicht zum Span.
# -------------------------------------------------------------
_SUFFIX_SEARCH_RE = re.compile(
    rf"(?P<suffix>{_SUFFIX_TOKEN_PATTERN})(?=$|[^A-Za-zÄÖÜäöüß])",
    re.IGNORECASE,
)


def extend_span_to_right_suffix(text: str, start: int, end: int) -> tuple[int, int]:
    """
    Erweitert einen ORG-Span nach rechts bis zum nächsten legalen
    Organisationssuffix, wenn der Zwischenbereich plausibel wie ein
    Organisationsname aussieht.

    Beispiele:
        "TransLog" -> "TransLog GmbH"
        "Bergmann" -> "Bergmann IT-Systeme GmbH"
        "Hansen" -> "Hansen & Reuter Logistik GmbH"
        "Franke Bau" -> "Franke Bau GmbH & Co KG"

    Nicht erweitert wird bei:
        - Zeilenumbruch vor dem Suffix
        - Satzende vor dem Suffix
        - offensichtlich unplausiblem Zwischeninhalt
    """

    if start < 0 or end <= start or end > len(text):
        return start, end

    # Fenster rechts vom Treffer.
    # Reicht für übliche Firmennamen + Suffix.
    tail = text[end:end + 80]

    if not tail:
        return start, end

    suffix_match = _SUFFIX_SEARCH_RE.search(tail)
    if suffix_match is None:
        return start, end

    # Alles zwischen aktuellem Span-Ende und Suffixanfang
    intermediate = tail[:suffix_match.start("suffix")]

    # Kein Zeilenumbruch im Zwischenbereich erlaubt.
    if "\n" in intermediate or "\r" in intermediate:
        return start, end

    # Wenn vor dem Suffix schon klar Satzende kommt, nicht erweitern.
    # Punkt ist nur dann KO, wenn danach normaler Satz weitergeht,
    # nicht wenn er direkt nach dem Suffix kommt.
    if any(ch in intermediate for ch in ":;!?"):
        return start, end

    # Zwischenbereich muss wie plausibler ORG-Text aussehen.
    if not _ALLOWED_INTERMEDIATE_RE.match(intermediate):
        return start, end

    # Zusätzlicher Schutz: nicht über extrem lange Wortketten laufen.
    candidate_extension = intermediate + suffix_match.group("suffix")
    token_count = len(re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", candidate_extension))
    if token_count > 8:
        return start, end

    new_end = end + suffix_match.end("suffix")
    return start, new_end