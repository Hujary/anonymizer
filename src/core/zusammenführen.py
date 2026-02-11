###     Treffer-Merge (Regex + NER Konfliktauflösung)
### __________________________________________________________________________
#
#  - Kombiniert Treffer aus Regex- und NER-Detektoren
#  - Sortiert initial nach Startposition und Länge (längere zuerst bei gleichem Start)
#  - Bevorzugt Regex gegenüber NER bei Overlap (wenn mindestens gleich lang)
#  - Entfernt vollständig enthaltene (nested) Treffer
#  - Liefert überlappungsfreie, start-sortierte Ergebnisliste


from typing import List
from .typen import Treffer


# Führt Regex- und NER-Treffer zusammen und löst Konflikte deterministisch auf
def zusammenführen(regex_treffer: List[Treffer], ner_treffer: List[Treffer]) -> List[Treffer]:

    # Alle Treffer kombinieren und nach (start, -länge) sortieren
    alles = sorted(
        regex_treffer + ner_treffer,
        key=lambda t: (t.start, -(t.ende - t.start)),
    )

    result: List[Treffer] = []

    # Erste Konfliktauflösung (Regex-Präferenz bei Overlap)
    for t in alles:
        konflikt = False

        for r in result:
            if t.überschneidet(r):

                # Regex gewinnt gegen NER, wenn mindestens gleich lang
                if (
                    t.source == "regex"
                    and r.source == "ner"
                    and t.länge() >= r.länge()
                ):
                    result.remove(r)
                    result.append(t)

                konflikt = True
                break

        if not konflikt:
            result.append(t)

    # Final nach Startposition sortieren
    result.sort(key=lambda t: t.start)

    # Entfernt vollständig enthaltene (nested) Treffer
    gefiltert: List[Treffer] = []

    for t in result:
        if not any(
            (t != u and t.start >= u.start and t.ende <= u.ende)
            for u in result
        ):
            gefiltert.append(t)

    return gefiltert