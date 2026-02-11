import re
from typing import Iterable, Tuple


def finde_location(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung einfacher Standortdaten (DE-fokussiert).

    Erkannt werden:
      - PLZ: 5-stellig
      - ORT: City-Name direkt nach PLZ (maskiert nur den Ortsnamen)
      - STRASSE: Straßenname + Hausnummer (zwei Varianten)

    Rückgabeformat:
      (start_index, end_index, label)
      -> Character-Offsets für Downstream-Masking
    """

    # ------------------------------------------------------------------
    # PLZ (Deutschland): exakt 5 Ziffern als eigenständiges Wort
    #
    # Risiko:
    #   - Matcht auch beliebige 5-stellige Zahlen (IDs, Zählerstände etc.)
    #   - Keine Plausibilitätsprüfung gegen PLZ-Bereiche
    # ------------------------------------------------------------------
    for m in re.finditer(r"\b\d{5}\b", text):
        yield (m.start(), m.end(), "PLZ")

    # ------------------------------------------------------------------
    # "PLZ ORT": 5-stellige PLZ gefolgt von einem oder mehreren Orts-Wörtern
    #
    # Maskiert wird NUR die benannte Gruppe "city", damit die PLZ separat
    # erkennbar bleibt und du doppelte/konfliktfreie Labels im Masker lösen kannst.
    #
    # Beispiele:
    #   "10115 Berlin"
    #   "80331 München"
    #   "50667 Köln"
    #   "01067 Dresden Altstadt" (mehrteiliger Ortsname)
    #
    # Einschränkung:
    #   - Nur einfache Groß-/Kleinschreibung-Heuristik, keine Gazetteer-Prüfung
    # ------------------------------------------------------------------
    plz_ort = re.compile(
        r"\b\d{5}\s+(?P<city>[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)*)\b"
    )
    for m in plz_ort.finditer(text):
        yield (m.start("city"), m.end("city"), "ORT")

    # ------------------------------------------------------------------
    # Straßen-Suffixe (typische echte Straßentypen im Deutschen)
    #
    # Hinweis:
    #   - str. wird bewusst unterstützt
    #   - "Strasse" ohne ß ist NICHT enthalten (wenn du das brauchst, ergänzen)
    # ------------------------------------------------------------------
    strassen_suffix = (
        r"(?:straße|str\.|weg|allee|platz|ring|gasse|ufer|damm|hof|steig|kai|chaussee|promenade|brücke)"
    )

    # ------------------------------------------------------------------
    # Variante A: "<Straßenname> <Suffix> <Hausnummer>"
    #
    # Beispiele:
    #   "Musterstraße 12"
    #   "Lange Allee 4a"
    #   "Berliner Str. 10"
    #
    # Schutzmaßnahmen:
    #   - Negative Lookbehind: nicht mitten in Tokens (E-Mail/Usernames) starten
    #   - Negative Lookahead: nicht direkt vor '@' enden (E-Mail-Bruchstücke)
    #
    # Schwäche:
    #   - Der Name-Teil ist relativ generisch; ohne Hausnummer wäre es zu noisy,
    #     daher ist Hausnummer hier Pflicht.
    # ------------------------------------------------------------------
    muster_a = re.compile(
        rf"""
        (?<![A-Za-z0-9._%+\-])                # nicht innerhalb von E-Mail/Usernamen starten
        [A-ZÄÖÜ][a-zäöüß\-]+
        (?:\s+[A-ZÄÖÜa-zäöüß\-]+)*            # weitere Bestandteile des Straßennamens
        \s+{strassen_suffix}
        \s+\d+[a-zA-Z]?                       # Hausnummer, optionaler Buchstabe (z.B. 12a)
        (?!@[A-Za-z0-9.\-])                   # nicht direkt vor @ stehen (keine Teile von E-Mails)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # ------------------------------------------------------------------
    # Variante B: Präposition + Name + Hausnummer (nur wenn Hausnummer vorhanden!)
    #
    # Beispiele:
    #   "Am Bahnhof 3"
    #   "Im Felde 12"
    #   "Zur Alten Schule 7"
    #
    # Motivation:
    #   - Viele deutsche Straßen beginnen mit Am/Im/An/Zur/Zum ...
    #
    # Risiko:
    #   - Ohne Hausnummer extrem viele False Positives (deshalb Pflicht).
    # ------------------------------------------------------------------
    muster_b = re.compile(
        r"""
        (?<![A-Za-z0-9._%+\-])                # nicht mitten in Token starten
        (?:Am|An|Im|In|Auf|Zu|Zur|Zum)\s+
        [A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)*
        \s+\d+[a-zA-Z]?                       # Hausnummer, optionaler Buchstabe
        (?!@[A-Za-z0-9.\-])                   # nicht direkt vor @ enden
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # ------------------------------------------------------------------
    # Kontext-Filter: Adress-Pattern nicht matchen, wenn in unmittelbarer Nähe
    # eine E-Mail-Adresse vorkommt.
    #
    # Hintergrund:
    #   - Diese Regexes sind bewusst "breiter". E-Mail-Kontexte liefern sonst
    #     immer wieder Zufallstreffer (Usernames, Domains, Pfade, etc.).
    #
    # Schwäche:
    #   - Grobe Heuristik: "@" im Umfeld => skip.
    #   - Kann echte Adressen in Signaturen mit E-Mail daneben ausblenden.
    # ------------------------------------------------------------------
    def skip_in_email_context(start: int, end: int) -> bool:
        segment = text[max(0, start - 40): min(len(text), end + 40)]
        return "@" in segment

    # ------------------------------------------------------------------
    # Treffer aus beiden Straßen-Varianten liefern.
    # Overlap-Auflösung ist nicht Aufgabe dieses Detektors.
    # ------------------------------------------------------------------
    for rx in (muster_a, muster_b):
        for m in rx.finditer(text):
            s, e = m.start(), m.end()
            if not skip_in_email_context(s, e):
                yield (s, e, "STRASSE")