###     Treffer-Datentyp (Immutable Span-Objekt für Detektion)
### __________________________________________________________________________
#
#  - Repräsentiert einen erkannten Textbereich (Span) im Originaltext
#  - Enthält Positionsdaten (start, ende), Label und Erkennungsquelle
#  - Unterstützt Overlap-Prüfung für Merge-/Prioritätslogik
#  - Immutable (frozen=True) → keine Seiteneffekte nach Erzeugung
#  - with_flags() erzeugt modifizierte Kopie statt Mutation


from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class Treffer:
    start: int
    ende: int
    label: str
    source: str
    from_regex: bool = False
    from_ner: bool = False
    text: str = ""

    validation_source: Optional[str] = None
    validation_status: Optional[str] = None
    validation_score: Optional[float] = None
    validation_threshold: Optional[float] = None
    validation_reason: Optional[str] = None
    validation_raw_score: Optional[float] = None
    validation_adjustment: Optional[float] = None

    def überschneidet(self, other: "Treffer") -> bool:
        return not (self.ende <= other.start or other.ende <= self.start)

    def länge(self) -> int:
        return self.ende - self.start

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

    def with_validation(
        self,
        *,
        source: Optional[str],
        status: Optional[str],
        score: Optional[float],
        threshold: Optional[float],
        reason: Optional[str],
        raw_score: Optional[float] = None,
        adjustment: Optional[float] = None,
    ) -> "Treffer":
        return replace(
            self,
            validation_source=source,
            validation_status=status,
            validation_score=score,
            validation_threshold=threshold,
            validation_reason=reason,
            validation_raw_score=raw_score,
            validation_adjustment=adjustment,
        )