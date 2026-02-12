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
    #
    # Fix:
    #   - KEIN \s (weil \s auch Zeilenumbrüche matcht) → nur [ \t]
    #   - Begrenzung nach City: Komma / Zeilenende / Stringende
    # ------------------------------------------------------------------
    plz_ort = re.compile(
        r"""
        \b\d{5}
        [ \t]+
        (?P<city>
            [A-ZÄÖÜ][a-zäöüß\-]+
            (?:[ \t]+[A-ZÄÖÜ][a-zäöüß\-]+)*
        )
        (?=(?:[ \t]*(?:,|$))|(?:\r?\n)|$)
        """,
        re.VERBOSE,
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
        r"(?i:straße|str\.|weg|allee|platz|ring|gasse|ufer|damm|hof|steig|kai|chaussee|promenade|brücke)"
    )

    # ------------------------------------------------------------------
    # Variante A: "<Straßenname> <Suffix> <Hausnummer>"
    #
    # Beispiele:
    #   "Berliner Str. 10"
    #   "Lange Allee 4a"
    #
    # Fix:
    #   - Kein \s in Tail/Trennern (nur [ \t]) → kein Zeilenumbruch-Fressen
    #   - Treffer wird nur aus Gruppe "addr" zurückgegeben
    # ------------------------------------------------------------------
    _street_particle = r"(?:am|an|auf|bei|im|in|vom|von|zur|zum|der|die|das|den|des|unter|ober|hinter|vor)"
    _street_word = r"(?:[A-ZÄÖÜ][a-zäöüß\-]+)"
    _street_tail = rf"(?:[ \t]+(?:{_street_word}|{_street_particle}))*"

    muster_a = re.compile(
        rf"""
        (?<![A-Za-z0-9._%+\-])
        (?P<addr>
            {_street_word}
            {_street_tail}
            [ \t]+{strassen_suffix}\b
            [ \t]+\d+[a-zA-Z]?
        )
        (?!@[A-Za-z0-9.\-])
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------------
    # Variante B: Präposition + Name + Hausnummer (nur wenn Hausnummer vorhanden!)
    #
    # Fix:
    #   - Nur [ \t] als Trenner → kein newline-skip
    # ------------------------------------------------------------------
    muster_b = re.compile(
        rf"""
        (?<![A-Za-z0-9._%+\-])
        (?P<addr>
            (?:Am|An|Im|In|Auf|Bei|Zu|Zur|Zum)[ \t]+
            {_street_word}
            (?:[ \t]+{_street_word})*
            [ \t]+\d+[a-zA-Z]?
        )
        (?!@[A-Za-z0-9.\-])
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------------
    # Variante C (Sonderfall): "<Straßenname+Suffix> <Hausnummer>"
    #
    # Fix:
    #   - Nur [ \t] vor Hausnummer → kein Zeilenumbruch-Fressen
    # ------------------------------------------------------------------
    muster_c = re.compile(
        rf"""
        (?<![A-Za-z0-9._%+\-])
        (?P<addr>
            [A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]*
            {strassen_suffix}\b
            [ \t]+\d+[a-zA-Z]?
        )
        (?!@[A-Za-z0-9.\-])
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------------
    # Variante D (Sonderfall): "<straßenname+suffix> <hausnummer>" in lowercase,
    # aber NUR wenn ein klarer Adress-Kontext davorsteht.
    #
    # Fix:
    #   - Kontext darf Zeilenanfang / newline enthalten
    #   - addr selbst bleibt auf einer Zeile (nur [ \t] vor Hausnummer)
    # ------------------------------------------------------------------
    _addr_prefix = r"(?:^|[\n\r]|(?:\b(?:adresse|anschrift)\s*:)|\b(?:in der|in die|in den|bei|auf|an|am|im)\b[ \t]+)"
    muster_d = re.compile(
        rf"""
        (?P<prefix>{_addr_prefix})
        (?P<addr>
            [a-zäöüß][a-zäöüß\-]*
            {strassen_suffix}\b
            [ \t]+\d+[a-zA-Z]?
        )
        """,
        re.VERBOSE,
    )

    # ------------------------------------------------------------------
    # Kontext-Filter: Adress-Pattern nicht matchen, wenn in unmittelbarer Nähe
    # eine E-Mail-Adresse vorkommt.
    # ------------------------------------------------------------------
    def skip_in_email_context(start: int, end: int) -> bool:
        segment = text[max(0, start - 40): min(len(text), end + 40)]
        return "@" in segment

    # ------------------------------------------------------------------
    # Treffer aus allen Straßen-Varianten liefern.
    # Overlap-Auflösung ist nicht Aufgabe dieses Detektors.
    # ------------------------------------------------------------------
    for rx in (muster_a, muster_b, muster_c, muster_d):
        for m in rx.finditer(text):
            s, e = m.start("addr"), m.end("addr")
            if not skip_in_email_context(s, e):
                yield (s, e, "STRASSE")