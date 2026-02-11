###     Detect + Mask Pipeline (Regex/NER/Dict Merge + Mask Output)
### __________________________________________________________________________
#
#  - Orchestriert Erkennung aus drei Quellen: Regex, spaCy-NER, manuelles Dictionary
#  - Aktivierung/Deaktivierung über Config-Flags (use_regex/use_ner/use_manual_dict)
#  - Merged Regex+NER über core.zusammenführen (Overlap-/Prioritätslogik zentral)
#  - Erzwingt Regex-Priorität für strukturierte Datentypen (IBAN, BIC, etc.)
#  - Erzwingt Dict-Priorität (manuelle Tokens überschreiben andere Treffer bei Overlap)
#  - Annotiert finale Treffer mit Quellenflags (from_regex/from_ner + source="dict")
#  - Anwenden(): erzeugt Mask-Strings je nach Modus (reversible/debug/default policy)


from __future__ import annotations

from typing import List, Tuple, Optional

from core.typen import Treffer
from core.zusammenführen import zusammenführen
from detectors.regex import finde_regex
from detectors.custom.manual_dict import finde_manual_tokens
from core.einstellungen import MASKIERUNGEN as MASK
from core import config


# Setzt from_regex/from_ner Flags anhand Overlap + Label-Gleichheit zu Originalquellen
def _flagge_quellen(merged: List[Treffer], regex_hits: List[Treffer], ner_hits: List[Treffer]) -> List[Treffer]:
    out: List[Treffer] = []
    for m in merged:
        fr = any(m.überschneidet(r) and m.label == r.label for r in regex_hits)
        fn = any(m.überschneidet(n) and m.label == n.label for n in ner_hits)
        out.append(m.with_flags(regex=fr, ner=fn))
    return out



# Strukturierte Typen: hier sind Regex-Matches typischerweise präziser als NER
STRUCT_TYPES = {"IBAN", "BIC", "TELEFON", "E_MAIL", "URL", "USTID", "RECHNUNGS_NUMMER", "PLZ", "DATUM"}



# Entfernt Nicht-Regex-Treffer, wenn sie strukturierte Regex-Treffer überlappen
def _prefer_regex_for_struct_types(merged: List[Treffer], regex_hits: List[Treffer]) -> List[Treffer]:
    keep: List[Treffer] = []
    for m in merged:
        overlaps_struct = any(m.überschneidet(r) and r.label.upper() in STRUCT_TYPES for r in regex_hits)
        if overlaps_struct and m.source != "regex":
            continue
        keep.append(m)
    return keep



# Dict-Treffer überschreiben alle anderen Treffer bei Overlap (manuell ist "hart")
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



# Ermittelt spaCy-Modellname aus Config (falls gesetzt)
def _resolve_spacy_model_name() -> Optional[str]:
    model = config.get("spacy_model", None)
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None



# Prüft, ob NER zur Laufzeit aktivierbar ist (spaCy importierbar + Modell als Package vorhanden)
def _is_ner_runtime_available() -> bool:
    try:
        import spacy  # noqa: F401
        from spacy.util import is_package
    except Exception:
        return False

    model_name = _resolve_spacy_model_name()
    if not model_name:
        return False

    try:
        return bool(is_package(model_name))
    except Exception:
        return False



# Führt NER aus und filtert Treffer direkt mit striktem Postfilter
def _run_ner(text: str, allowed_labels: List[str]) -> List[Treffer]:
    try:
        from detectors.ner import finde_ner
        from detectors.ner.filters import filter_ner_strict
    except Exception:
        return []

    raw_ner = [Treffer(s, e, l, "ner", from_ner=True) for s, e, l in finde_ner(text)]
    return filter_ner_strict(text, raw_ner, allowed_labels=allowed_labels)



# Erkennung: sammelt Treffer aus aktivierten Quellen und führt Prioritätsregeln aus
def erkenne(text: str) -> List[Treffer]:
    flags = config.get_flags()

    regex_treffer: List[Treffer] = []
    ner_treffer: List[Treffer] = []
    dict_treffer: List[Treffer] = []

    if flags.get("use_regex", True):
        regex_treffer = [Treffer(s, e, l, "regex", from_regex=True) for s, e, l in finde_regex(text)]

    if flags.get("use_ner", True):
        allowed = config.get("ner_labels", [])
        if allowed and _is_ner_runtime_available():
            ner_treffer = _run_ner(text, allowed_labels=allowed)
        else:
            ner_treffer = []

    if flags.get("use_manual_dict", True):
        dict_treffer = finde_manual_tokens(text)

    if not regex_treffer and not ner_treffer and not dict_treffer:
        return []

    # Regex+NER werden zusammengeführt, Dict kommt später als "override"
    if regex_treffer or ner_treffer:
        merged = zusammenführen(regex_treffer, ner_treffer)
    else:
        merged = []

    # Strukturierte Typen: wenn Regex etwas gefunden hat, wird das gegenüber anderen Quellen bevorzugt
    if regex_treffer and flags.get("use_regex", True):
        merged = _prefer_regex_for_struct_types(merged, regex_treffer)

    # Dict überschreibt bei Overlap alles andere
    if dict_treffer:
        merged = _apply_dict_priority(merged, dict_treffer)

    # Finale Treffer mit Quellenflags annotieren (für Debug-Mask / UI)
    return _flagge_quellen(merged, regex_treffer, ner_treffer)



# Mask-Anwendung: ersetzt Treffer-Spans im Text durch Mask-Labels (reversible/debug/policy)
def anwenden(text: str, treffer: List[Treffer], *, reversible: bool) -> str:
    debug_mask = config.get("debug_mask", False)

    teile: List[str] = []
    pos = 0

    for t in treffer:
        teile.append(text[pos:t.start])

        # Reversible: nur Label im Token, echtes Mapping passiert außerhalb (SessionManager/Wrapper)
        if reversible:
            mask_label = f"[{t.label}]"

        # Nicht-reversible: optional Debug-Labels oder Policy-basierte Masking-Strings
        else:
            if debug_mask:
                suffix_parts = []
                if t.from_regex:
                    suffix_parts.append("REGEX")
                if t.from_ner:
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



# API: kombiniert erkenne() + anwenden() und liefert (masked_text, trefferliste)
def maskiere(text: str, *, reversible: bool = False) -> Tuple[str, List[Treffer]]:
    t = erkenne(text)
    out = anwenden(text, t, reversible=reversible)
    return out, t