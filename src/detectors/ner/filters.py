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

    if not flags.get("use_ner", True):
        return []

    allowed = config.get("ner_labels", [])
    allowed_set = _normalize_labels(allowed)

    if not allowed_set:
        return []

    loc_hits: List[Treffer] = []
    passthrough_hits: List[Treffer] = []

    for h in hits:
        label = str(h.label).strip().upper()

        if label == "LOC":
            loc_hits.append(h)
            continue

        if label in {"PER", "ORG"}:
            passthrough_hits.append(h)
            continue

    use_post = bool(config.get("use_ner_postprocessing", True))
    if use_post:
        loc_hits = postprocess_hits(text, loc_hits)

    refined_loc_hits = refine_ner_labels(text, loc_hits)

    current_hits = passthrough_hits + refined_loc_hits
    current_hits.sort(key=lambda t: (t.start, t.ende, t.label))

    return apply_policy_labels(current_hits, allowed_set)