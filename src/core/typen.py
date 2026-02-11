###     Treffer-Datentyp (Immutable Span-Objekt für Detektion)
### __________________________________________________________________________
#
#  - Repräsentiert einen erkannten Textbereich (Span) im Originaltext
#  - Enthält Positionsdaten (start, ende), Label und Erkennungsquelle
#  - Unterstützt Overlap-Prüfung für Merge-/Prioritätslogik
#  - Immutable (frozen=True) → keine Seiteneffekte nach Erzeugung
#  - with_flags() erzeugt modifizierte Kopie statt Mutation


from dataclasses import dataclass, replace


# Beschreibt einen erkannten Datenbereich im Text (z. B. E-Mail, IBAN, PER)
@dataclass(frozen=True)
class Treffer:
    start: int          # Startindex (inklusive)
    ende: int           # Endindex (exklusive)
    label: str          # Entitätstyp (z. B. "E_MAIL", "PER")
    source: str         # Primäre Quelle ("regex", "ner", "dict")
    from_regex: bool = False  # True, wenn Regex-Detektor beteiligt war
    from_ner: bool = False    # True, wenn NER-Detektor beteiligt war

    # Prüft, ob zwei Spans sich überlappen (Intervall-Logik)
    def überschneidet(self, other: "Treffer") -> bool:
        return not (self.ende <= other.start or other.ende <= self.start)

    # Liefert Länge des Spans (wird u. a. für Priorisierung verwendet)
    def länge(self) -> int:
        return self.ende - self.start

    # Erzeugt neue Instanz mit geänderten Flags (keine Mutation des Originals)
    def with_flags(
        self,
        *,
        regex: bool | None = None,
        ner: bool | None = None,
    ) -> "Treffer":
        return replace(
            self,
            from_regex=self.from_regex if regex is None else regex,
            from_ner=self.from_ner if ner is None else ner,
        )