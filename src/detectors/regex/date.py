import re
from typing import Iterable, Tuple


def finde_date(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung gängiger Datumsformate (DE + EN).

    Erkannt werden:
      - ISO: 2024-12-01
      - Deutsch numerisch: 17.10.2024
      - Deutsch lang: 17. Oktober 2024
      - Englisch: March 12, 2025 / Dec 5, 2023
      - Englisch invertiert: 12 March 2025

    Rückgabe:
      (start_index, end_index, "DATUM")

    Hinweis:
      - Keine Validierung realer Kalendertage (z.B. 31.02.2024 wird gematcht)
      - Keine Kontextprüfung (z.B. Versionsnummern)
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
        # ------------------------------------------------------------------
        re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"),

        # ------------------------------------------------------------------
        # Deutsch ausgeschrieben: 17. Oktober 2024
        #
        # Case-insensitive wegen Monatsnamen
        # ------------------------------------------------------------------
        re.compile(rf"\b\d{{1,2}}\.\s*{monate}\s*\d{{4}}\b", re.IGNORECASE),

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