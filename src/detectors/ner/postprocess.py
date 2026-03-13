from __future__ import annotations

from typing import Callable, Dict, List

from core.typen import Treffer
from .postprocess_helpers.loc.process_loc_hit import process_loc_hit
from .postprocess_helpers.org.process_org_hit import process_org_hit
from .postprocess_helpers.per.process_per_hit import process_per_hit
from .postprocess_helpers.shared.remove_duplicate_hits import remove_duplicate_hits


# Mapping der Label auf ihre jeweiligen Postprocessing-Funktionen
_POSTPROCESSORS: Dict[str, Callable[[str, Treffer], Treffer | None]] = {
    "LOC": process_loc_hit,
    "PER": process_per_hit,
    "ORG": process_org_hit,
}


def postprocess_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    # Führt für jeden Treffer das passende Postprocessing-Modul aus
    result: List[Treffer] = []

    for hit in hits:
        label = str(hit.label).strip().upper()

        # Passenden Postprocessor anhand des Labels auswählen
        processor = _POSTPROCESSORS.get(label)

        if processor is None:
            continue

        # Treffer durch das jeweilige Modul verarbeiten
        processed = processor(text, hit)

        # Treffer verwerfen, wenn Postprocessor None zurückgibt
        if processed is None:
            continue

        result.append(processed)

    # Doppelte Treffer entfernen
    result = remove_duplicate_hits(result)

    # Treffer stabil nach Position sortieren
    result.sort(key=lambda t: (t.start, t.ende, t.label))

    return result