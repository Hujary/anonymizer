from __future__ import annotations

from typing import Callable, Dict, List

from core.typen import Treffer
from .postprocess_helpers.loc.process_loc_hit import process_loc_hit
from .postprocess_helpers.org.process_org_hit import process_org_hit
from .postprocess_helpers.per.process_per_hit import process_per_hit
from .postprocess_helpers.shared.remove_duplicate_hits import remove_duplicate_hits


# Mehrere Labels dürfen denselben Postprocessor verwenden.
# LOC und STRASSE laufen bewusst beide durch dieselbe Logik,
# weil dort entschieden wird, ob ein Treffer am Ende LOC oder STRASSE bleibt.
_POSTPROCESSORS: Dict[str, Callable[[str, Treffer], Treffer | None]] = {
    "LOC": process_loc_hit,
    "STRASSE": process_loc_hit,
    "PER": process_per_hit,
    "ORG": process_org_hit,
}


def postprocess_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    result: List[Treffer] = []

    for hit in hits:
        # Label robust normieren, damit z. B. "loc" und "LOC" identisch behandelt werden.
        label = str(hit.label).strip().upper()
        processor = _POSTPROCESSORS.get(label)

        # Treffer ohne registrierten Processor werden ignoriert.
        # Das ist absichtlich strikt: unbekannte Labels sollen nicht stillschweigend
        # unverändert durchgeschleust werden.
        if processor is None:
            continue

        # Label-spezifisches Postprocessing ausführen.
        processed = processor(text, hit)

        # None bedeutet: Treffer wurde bewusst verworfen.
        if processed is None:
            continue

        result.append(processed)

    # Durch Normalisierung / Erweiterung können Dubletten entstehen.
    result = remove_duplicate_hits(result)

    # Stabile Sortierung nach Textposition, damit Folgekomponenten deterministisch arbeiten.
    result.sort(key=lambda t: (t.start, t.ende, t.label))

    return result