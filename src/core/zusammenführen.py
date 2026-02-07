from typing import List
from .typen import Treffer

# Führt Treffer aus Regex und NER zusammen, entfernt Überschneidungen und Dopplungen.
def zusammenführen(regex_treffer: List[Treffer], ner_treffer: List[Treffer]) -> List[Treffer]:
    alles = sorted(regex_treffer + ner_treffer, key=lambda t: (t.start, -(t.ende - t.start)))
    result: List[Treffer] = []
    for t in alles:
        konflikt = False
        for r in result:
            if t.überschneidet(r):
                if t.source == "regex" and r.source == "ner" and t.länge() >= r.länge():
                    result.remove(r)
                    result.append(t)
                konflikt = True
                break
        if not konflikt:
            result.append(t)
    result.sort(key=lambda t: t.start)
    gefiltert: List[Treffer] = []
    for t in result:
        if not any((t != u and t.start >= u.start and t.ende <= u.ende) for u in result):
            gefiltert.append(t)
    return gefiltert