from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from core import config
from core.einstellungen import MASKIERUNGEN as MASK
from core.typen import Treffer
from core.zusammenführen import zusammenführen

from detectors.regex import finde_regex
from detectors.custom.manual_dict import finde_manual_tokens
from pipeline.validation import validate_regex_hits, filter_effective_hits_for_masking


MaskingPhaseCallback = Callable[[str], None]


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


def _emit_phase(on_phase: Optional[MaskingPhaseCallback], value: str) -> None:
    if on_phase is None:
        return

    try:
        on_phase(value)
    except Exception:
        pass


def _run_ner(text: str) -> List[Treffer]:
    try:
        from detectors.ner import finde_ner
    except Exception:
        return []

    hits: List[Treffer] = []

    for s, e, l in finde_ner(text):
        hits.append(Treffer(s, e, l, "ner", from_ner=True, text=text[s:e]))

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


def erkenne(text: str, *, on_phase: Optional[MaskingPhaseCallback] = None) -> List[Treffer]:
    flags = config.get_flags()

    regex_treffer: List[Treffer] = []
    ner_treffer: List[Treffer] = []
    dict_treffer: List[Treffer] = []

    if flags.get("use_regex", True):
        regex_treffer = [
            Treffer(s, e, l, "regex", from_regex=True, text=text[s:e])
            for s, e, l in finde_regex(text)
        ]
        regex_treffer = validate_regex_hits(text, regex_treffer)

    if flags.get("use_ner", True) and _is_ner_runtime_available():
        try:
            from detectors.ner.model_manager import MODEL_MANAGER
            ner_is_loaded = MODEL_MANAGER.is_current_model_loaded()
        except Exception:
            ner_is_loaded = True

        if not ner_is_loaded:
            _emit_phase(on_phase, "NER-Initialisierung")
        else:
            _emit_phase(on_phase, "Maskierung")

        ner_treffer = _run_ner(text)
    else:
        _emit_phase(on_phase, "Maskierung")
        ner_treffer = []

    if flags.get("use_manual_dict", True):
        dict_raw = finde_manual_tokens(text)
        dict_treffer = [
            Treffer(
                h.start,
                h.ende,
                h.label,
                getattr(h, "source", "dict"),
                from_regex=getattr(h, "from_regex", False),
                from_ner=getattr(h, "from_ner", False),
                text=text[h.start:h.ende],
                validation_source=getattr(h, "validation_source", None),
                validation_status=getattr(h, "validation_status", None),
                validation_score=getattr(h, "validation_score", None),
                validation_threshold=getattr(h, "validation_threshold", None),
                validation_reason=getattr(h, "validation_reason", None),
                validation_raw_score=getattr(h, "validation_raw_score", None),
                validation_adjustment=getattr(h, "validation_adjustment", None),
            )
            for h in dict_raw
        ]

    if not regex_treffer and not ner_treffer and not dict_treffer:
        return []

    effective_regex_hits = filter_effective_hits_for_masking(regex_treffer)

    if effective_regex_hits or ner_treffer:
        merged = zusammenführen(effective_regex_hits, ner_treffer)
    else:
        merged = []

    if dict_treffer:
        merged = _apply_dict_priority(merged, dict_treffer)

    merged = _flagge_quellen(merged, effective_regex_hits, ner_treffer)

    merged_by_span = {(m.start, m.ende, m.label): m for m in merged}

    for rx in regex_treffer:
        key = (rx.start, rx.ende, rx.label)
        if key in merged_by_span:
            current = merged_by_span[key]
            merged_by_span[key] = Treffer(
                current.start,
                current.ende,
                current.label,
                current.source,
                from_regex=current.from_regex,
                from_ner=current.from_ner,
                text=current.text or rx.text,
                validation_source=rx.validation_source,
                validation_status=rx.validation_status,
                validation_score=rx.validation_score,
                validation_threshold=rx.validation_threshold,
                validation_reason=rx.validation_reason,
                validation_raw_score=rx.validation_raw_score,
                validation_adjustment=rx.validation_adjustment,
            )

    out = list(merged_by_span.values())
    out.sort(key=lambda t: t.start)
    return out


def anwenden(text: str, treffer: List[Treffer], *, reversible: bool) -> str:
    debug_mask = config.get("debug_mask", False)

    teile: List[str] = []
    pos = 0

    effective_hits = filter_effective_hits_for_masking(treffer)

    for t in effective_hits:
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


def maskiere(
    text: str,
    *,
    reversible: bool = False,
    on_phase: Optional[MaskingPhaseCallback] = None,
) -> Tuple[str, List[Treffer]]:
    t = erkenne(text, on_phase=on_phase)
    _emit_phase(on_phase, "Maskierung")
    out = anwenden(text, t, reversible=reversible)
    _emit_phase(on_phase, "")
    return out, t