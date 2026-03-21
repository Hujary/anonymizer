from __future__ import annotations

from typing import List, Optional, Tuple

from core import config
from core.einstellungen import MASKIERUNGEN as MASK
from core.typen import Treffer
from core.zusammenführen import zusammenführen

from detectors.regex import finde_regex
from detectors.custom.manual_dict import finde_manual_tokens


def _resolve_ner_backend() -> str:
    backend = config.get("ner_backend", "spacy")
    if isinstance(backend, str):
        backend = backend.strip().lower()
    else:
        backend = "spacy"

    if backend not in ("spacy", "flair"):
        return "spacy"

    return backend


def _resolve_ner_model_name() -> Optional[str]:
    model = config.get("ner_model", None)
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def _is_spacy_model_available(model_name: str) -> bool:
    try:
        from spacy.util import is_package
    except Exception:
        return False

    try:
        return bool(is_package(model_name))
    except Exception:
        return False


def _is_flair_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("flair") is not None
    except Exception:
        return False


def _is_ner_runtime_available() -> bool:
    backend = _resolve_ner_backend()
    model_name = _resolve_ner_model_name()

    if not model_name:
        return False

    if backend == "spacy":
        return _is_spacy_model_available(model_name)

    if backend == "flair":
        return _is_flair_available()

    return False


def _run_ner(text: str) -> List[Treffer]:
    try:
        from detectors.ner import finde_ner
    except Exception:
        return []

    hits: List[Treffer] = []

    for s, e, l in finde_ner(text):
        hits.append(Treffer(s, e, l, "ner", from_ner=True))

    return hits


def _overlaps_any(a: Treffer, hits: List[Treffer]) -> bool:
    return any(a.überschneidet(h) for h in hits)


def _flagge_quellen(
    merged: List[Treffer],
    regex_hits: List[Treffer],
    ner_hits: List[Treffer],
) -> List[Treffer]:
    out: List[Treffer] = []

    for m in merged:
        fr0 = bool(getattr(m, "from_regex", False)) or getattr(m, "source", "") == "regex"
        fn0 = bool(getattr(m, "from_ner", False)) or getattr(m, "source", "") == "ner"

        fr = fr0 or _overlaps_any(m, regex_hits)
        fn = fn0 or _overlaps_any(m, ner_hits)

        out.append(m.with_flags(regex=fr, ner=fn))

    return out


def _apply_dict_priority(base_hits: List[Treffer], dict_hits: List[Treffer]) -> List[Treffer]:
    if not dict_hits:
        return base_hits

    filtered_base: List[Treffer] = []

    for h in base_hits:
        if any(h.überschneidet(d) for d in dict_hits):
            continue
        filtered_base.append(h)

    final_hits = filtered_base + list(dict_hits)
    final_hits.sort(key=lambda t: t.start)
    return final_hits


def erkenne(text: str) -> List[Treffer]:
    flags = config.get_flags()

    regex_treffer: List[Treffer] = []
    ner_treffer: List[Treffer] = []
    dict_treffer: List[Treffer] = []

    if flags.get("use_regex", True):
        regex_treffer = [
            Treffer(s, e, l, "regex", from_regex=True)
            for s, e, l in finde_regex(text)
        ]

    if flags.get("use_ner", True) and _is_ner_runtime_available():
        ner_treffer = _run_ner(text)
    else:
        ner_treffer = []

    if flags.get("use_manual_dict", True):
        dict_treffer = finde_manual_tokens(text)

    if not regex_treffer and not ner_treffer and not dict_treffer:
        return []

    if regex_treffer or ner_treffer:
        merged = zusammenführen(regex_treffer, ner_treffer)
    else:
        merged = []

    if dict_treffer:
        merged = _apply_dict_priority(merged, dict_treffer)

    return _flagge_quellen(merged, regex_treffer, ner_treffer)


def anwenden(text: str, treffer: List[Treffer], *, reversible: bool) -> str:
    debug_mask = config.get("debug_mask", False)

    teile: List[str] = []
    pos = 0

    for t in treffer:
        teile.append(text[pos:t.start])

        if reversible:
            mask_label = f"[{t.label}]"
        else:
            if debug_mask:
                suffix_parts: List[str] = []
                if getattr(t, "from_regex", False):
                    suffix_parts.append("REGEX")
                if getattr(t, "from_ner", False):
                    suffix_parts.append("NER")
                if getattr(t, "source", "") == "dict":
                    suffix_parts.append("DICT")
                suffix = "_".join(suffix_parts) if suffix_parts else "UNK"
                mask_label = f"[{t.label}_{suffix}]"
            else:
                mask_label = MASK.get(t.label, "[MASK]")

        teile.append(mask_label)
        pos = t.ende

    teile.append(text[pos:])
    return "".join(teile)


def maskiere(text: str, *, reversible: bool = False) -> Tuple[str, List[Treffer]]:
    t = erkenne(text)
    out = anwenden(text, t, reversible=reversible)
    return out, t