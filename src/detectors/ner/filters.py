from __future__ import annotations

from typing import Iterable, List, Set

from core import config
from core.typen import Treffer
from .label_refiner import refine_ner_labels
from .postprocess import postprocess_hits


def _normalize_labels(labels: object) -> Set[str]:
    if not isinstance(labels, (list, tuple, set)):
        return set()

    out: Set[str] = set()

    for label in labels:
        s = str(label).strip().upper()
        if s:
            out.add(s)

    return out


def apply_policy_labels(hits: List[Treffer], allowed_labels: Iterable[str]) -> List[Treffer]:
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
    flags = config.get_flags()

    print("\n==================== FILTERS ====================")
    print(f"FILTERS | use_ner={flags.get('use_ner', True)!r}")
    print(f"FILTERS | use_ner_postprocessing={flags.get('use_ner_postprocessing', True)!r}")

    if not flags.get("use_ner", True):
        print("FILTERS | NER deaktiviert")
        print("=================================================\n")
        return []

    allowed = config.get("ner_labels", [])
    allowed_set = _normalize_labels(allowed)

    print(f"FILTERS | allowed_raw={allowed!r}")
    print(f"FILTERS | allowed_set={sorted(allowed_set)!r}")

    if not allowed_set:
        print("FILTERS | keine erlaubten Labels")
        print("=================================================\n")
        return []

    current_hits: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()
        span = text[h.start:h.ende]

        print(
            f"FILTERS | raw_hit label={label:<10} "
            f"| start={h.start:<4} "
            f"| ende={h.ende:<4} "
            f"| text={span!r}"
        )

        if label in {"LOC", "PER", "ORG"}:
            current_hits.append(h)

    print(f"FILTERS | kept_before_post={len(current_hits)}")

    use_post = bool(config.get("use_ner_postprocessing", True))
    print(f"FILTERS | use_post_bool={use_post!r}")

    if use_post:
        current_hits = postprocess_hits(text, current_hits)
        print(f"FILTERS | after_postprocess={len(current_hits)}")

    current_hits = refine_ner_labels(text, current_hits)
    print(f"FILTERS | after_refine={len(current_hits)}")

    final_hits = apply_policy_labels(current_hits, allowed_set)
    print(f"FILTERS | after_policy={len(final_hits)}")
    print("=================================================\n")

    return final_hits