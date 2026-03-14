from __future__ import annotations

from typing import Iterable, List, Set

from core import config
from core.typen import Treffer
from .label_refiner import refine_ner_labels
from .postprocess import postprocess_hits


def _normalize_labels(labels: object) -> Set[str]:
    # Wandelt eine Liste beliebiger Label-Werte in ein normiertes Set um
    # (Großschreibung, Whitespace entfernt)
    if not isinstance(labels, (list, tuple, set)):
        return set()

    out: Set[str] = set()

    for label in labels:
        s = str(label).strip().upper()
        if s:
            out.add(s)

    return out


def apply_policy_labels(hits: List[Treffer], allowed_labels: Iterable[str]) -> List[Treffer]:
    # Filtert Treffer anhand der erlaubten Label aus der Policy
    allowed = _normalize_labels(list(allowed_labels))

    if not allowed:
        return []

    out: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()

        if label in allowed:
            out.append(h)

    return out


def clean_ner_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    # Lädt Runtime-Flags aus der Konfiguration
    flags = config.get_flags()

    # Wenn NER global deaktiviert ist → keine Treffer zurückgeben
    if not flags.get("use_ner", True):
        return []

    # Erlaubte Labels aus der Konfiguration laden
    allowed = config.get("ner_labels", [])
    allowed_set = _normalize_labels(allowed)

    if not allowed_set:
        return []

    # Zuerst nur grob auf Labels eingrenzen, die wir überhaupt weiterverarbeiten wollen.
    # MISC bleibt hier bewusst erhalten, damit der Refiner daraus z.B. ORG machen kann.
    current_hits: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()

        if label in {"LOC", "PER", "ORG", "MISC"}:
            current_hits.append(h)

    # WICHTIG:
    # Label-Refinement vor dem Postprocessing und vor der finalen Filterung.
    # So können brauchbare MISC-Treffer in echte Labels umklassifiziert werden.
    current_hits = refine_ner_labels(text, current_hits)

    # Danach nur noch die fachlich relevanten Labels behalten.
    # Nicht umklassifizierte MISC-Treffer werden hier verworfen.
    refined_hits: List[Treffer] = []

    for h in current_hits:
        label = str(h.label).strip().upper()

        if label in {"LOC", "PER", "ORG", "STRASSE"}:
            refined_hits.append(h)

    current_hits = refined_hits

    # Optionales NER-Postprocessing (Span-Korrektur, Blacklists, etc.)
    use_post = bool(config.get("use_ner_postprocessing", True))

    if use_post:
        current_hits = postprocess_hits(text, current_hits)

    # Finale Policy-Filterung anhand der erlaubten Labels
    final_hits = apply_policy_labels(current_hits, allowed_set)

    return final_hits