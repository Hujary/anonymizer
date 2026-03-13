from __future__ import annotations

from typing import Callable, Dict, List

from core.typen import Treffer
from .postprocess_helpers.loc.process_loc_hit import process_loc_hit
from .postprocess_helpers.org.process_org_hit import process_org_hit
from .postprocess_helpers.per.process_per_hit import process_per_hit
from .postprocess_helpers.shared.remove_duplicate_hits import remove_duplicate_hits


_POSTPROCESSORS: Dict[str, Callable[[str, Treffer], Treffer | None]] = {
    "LOC": process_loc_hit,
    "PER": process_per_hit,
    "ORG": process_org_hit,
}


def postprocess_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    result: List[Treffer] = []

    for hit in hits:
        label = str(hit.label).strip().upper()

        processor = _POSTPROCESSORS.get(label)
        if processor is None:
            continue

        processed = processor(text, hit)
        if processed is None:
            continue

        result.append(processed)

    result = remove_duplicate_hits(result)
    result.sort(key=lambda t: (t.start, t.ende, t.label))
    return result