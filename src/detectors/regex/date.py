import re
from typing import Iterable, Tuple


def finde_date(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung gängiger Datumsformate (DE + EN).

    Erkannt werden:
      - ISO: 2024-12-01
      - Deutsch numerisch: 17.10.2024
      - Deutsch numerisch ohne Jahr: 17.10
      - Deutsch lang: 17. Oktober 2024
      - Deutsch lang ohne Jahr: 17. Oktober / 17. Nov.
      - Englisch: March 12, 2025 / Dec 5, 2023
      - Englisch invertiert: 12 March 2025

    Rückgabe:
      (start_index, end_index, "DATUM")

    Hinweis:
      - Keine vollständige Validierung realer Kalendertage (z.B. 31.02.2024 wird gematcht)
      - FIX: Versions-/Kettenformate wie "v2.8.1" erzeugen KEIN False Positive mehr
    """

    # ------------------------------------------------------------------
    # Monatsnamen (Deutsch + Englisch, kurz und lang)
    #
    # Enthält:
    #   - Deutsche Varianten (März, Oktober, Dezember etc.)
    #   - Englische Varianten (March, Dec, September etc.)
    #
    # Einschränkung:
    #   - Keine alternative Schreibweise "Maerz"
    #   - Keine Sprachkontextprüfung
    # ------------------------------------------------------------------
    monate = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mär(?:z)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Okt(?:ober)?|Oct(?:ober)?|Nov(?:ember)?|Dez(?:ember)?|Dec(?:ember)?)"
    )

    patterns = [
        # ------------------------------------------------------------------
        # ISO-Format: YYYY-MM-DD
        #
        # Einschränkung:
        #   - Keine Validierung von Monats-/Tagesbereich
        #   - Jahr nur 1900–2099
        # ------------------------------------------------------------------
        re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),

        # ------------------------------------------------------------------
        # Deutsch numerisch: 17.10.2024 / 17-10-24 / 17/10/2024
        #
        # Risiko:
        #   - Kann auch Versionsnummern matchen (z.B. 1.2.2024)
        #
        # FIX:
        #   - Tag/Monat grob range-validiert (1–31 / 1–12)
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Deutsch numerisch ohne Jahr: 17.10
        #
        # FIX:
        #   - Tag/Monat range-validiert (1–31 / 1–12)
        #   - Kein Match, wenn direkt davor "Ziffer." steht
        #     → verhindert "v2.8.1" => kein Treffer für "8.1"
        #   - Kein Match, wenn direkt danach ".Ziffer" folgt
        #     → verhindert "8.1.3" (Versionskette)
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Monat/Jahr: 07/2021 / 3-2017
        #
        # Typisch in Lebensläufen für Beschäftigungszeiträume.
        #
        # FIX:
        #   - Monat range-validiert (1–12)
        #   - Jahr 4-stellig
        #   - Kein Match, wenn davor oder danach weitere Ziffern folgen
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Deutsch ausgeschrieben: 17. Oktober 2024
        #
        # Case-insensitive wegen Monatsnamen
        # ------------------------------------------------------------------
        re.compile(rf"\b\d{{1,2}}\.\s*{monate}\s*\d{{4}}\b", re.IGNORECASE),

        # ------------------------------------------------------------------
        # Deutsch ausgeschrieben ohne Jahr: 17. Oktober / 17. Nov.
        #
        # Risiko:
        #   - Keine Kontextprüfung (kann theoretisch falsch-positive Matches erzeugen)
        # ------------------------------------------------------------------
        re.compile(rf"\b\d{{1,2}}\.\s*{monate}\b", re.IGNORECASE),

        # ------------------------------------------------------------------
        # Englisch: March 12, 2025 / Dec 5, 2023
        #
        # Format: <Month> <Day>, <Year>
        # ------------------------------------------------------------------
        re.compile(rf"\b{monate}\s+\d{{1,2}},\s*\d{{4}}\b", re.IGNORECASE),

        # ------------------------------------------------------------------
        # Englisch invertiert: 12 March 2025
        #
        # Format: <Day> <Month> <Year>
        # ------------------------------------------------------------------
        re.compile(rf"\b\d{{1,2}}\s+{monate}\s+\d{{4}}\b", re.IGNORECASE),
    ]

    # ----------------------------------------------------------------------
    # Alle Patterns anwenden.
    # Overlap-Handling ist Aufgabe der Masking-Pipeline.
    # ----------------------------------------------------------------------
    for rx in patterns:
        for m in rx.finditer(text):
            yield (m.start(), m.end(), "DATUM")