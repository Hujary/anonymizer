from __future__ import annotations

from typing import Callable, Dict, List

from core.typen import Treffer
from .postprocess_helpers.loc.process_loc_hit import process_loc_hit
from .postprocess_helpers.org.process_org_hit import process_org_hit
from .postprocess_helpers.per.process_per_hit import process_per_hit
from .postprocess_helpers.shared.remove_duplicate_hits import remove_duplicate_hits


print("DEBUG: LOADED src/detectors/ner/postprocess.py")


_POSTPROCESSORS: Dict[str, Callable[[str, Treffer], Treffer | None]] = {
    "LOC": process_loc_hit,
    "PER": process_per_hit,
    "ORG": process_org_hit,
}


def postprocess_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    print("\n==================== POSTPROCESS ====================")
    print(f"POSTPROCESS | input_hits={len(hits)}")

    result: List[Treffer] = []

    for hit in hits:
        label = str(hit.label).strip().upper()
        span = text[hit.start:hit.ende]

        print(
            f"POSTPROCESS | in label={label:<10} "
            f"| start={hit.start:<4} "
            f"| ende={hit.ende:<4} "
            f"| text={span!r}"
        )

        processor = _POSTPROCESSORS.get(label)
        print(f"POSTPROCESS | processor_found={processor is not None!r} for label={label}")

        if processor is None:
            continue

        processed = processor(text, hit)

        if processed is None:
            print(f"POSTPROCESS | dropped label={label} text={span!r}")
            continue

        processed_span = text[processed.start:processed.ende]
        print(
            f"POSTPROCESS | out label={processed.label:<10} "
            f"| start={processed.start:<4} "
            f"| ende={processed.ende:<4} "
            f"| text={processed_span!r}"
        )

        result.append(processed)

    result = remove_duplicate_hits(result)
    result.sort(key=lambda t: (t.start, t.ende, t.label))

    print(f"POSTPROCESS | final_hits={len(result)}")
    print("=====================================================\n")

    return result