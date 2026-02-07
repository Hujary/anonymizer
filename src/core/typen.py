###     Hilfsdatei zum umwandeln von Treffern (PD-Daten) in ein Objekt 
### __________________________________________________________________________

from dataclasses import dataclass, replace

# beschreibt einen erkannten Datenbereich im Text (z. B. E-Mail, IBAN)
@dataclass(frozen=True)
class Treffer:
    start: int     # Startposition im Text
    ende: int      # Endposition im Text
    label: str     # Datentyp (z. B. "E_MAIL")
    source: str    # Erkennungsquelle (z. B. "regex" oder "ner")
    from_regex: bool = False   # Flag: wurde vom Regex-Detektor gefunden
    from_ner: bool = False     # Flag: wurde vom NER-Detektor gefunden

    # prüft, ob sich zwei Treffer überlappen
    def überschneidet(self, other: "Treffer") -> bool:
        return not (self.ende <= other.start or other.ende <= self.start)

    # gibt die Länge des gefundenen Bereichs zurück
    def länge(self) -> int:
        return self.ende - self.start

    # erzeugt eine Kopie mit veränderten Flags (immutable Dataclass)
    def with_flags(self, *, regex: bool | None = None, ner: bool | None = None) -> "Treffer":
        return replace(
            self,
            from_regex=self.from_regex if regex is None else regex,
            from_ner=self.from_ner if ner is None else ner,
        )