###     NER-Detektor (spaCy) mit umschaltbarem Modell und Cache
### __________________________________________________________________________

from __future__ import annotations
from typing import Iterable, Tuple, Dict, Optional
import threading
import spacy

from core.einstellungen import SPACY_MODELL, NER_PRESETS

_cache: Dict[str, "spacy.Language"] = {}
_lock = threading.Lock()
_current_model: str = SPACY_MODELL

def _resolve_model(name_or_preset: str) -> str:
    if name_or_preset in NER_PRESETS:
        return NER_PRESETS[name_or_preset]
    return name_or_preset

def get_current_model() -> str:
    return _current_model

def set_spacy_model(name_or_preset: str) -> str:
    global _current_model
    model = _resolve_model(name_or_preset)
    with _lock:
        _current_model = model
    return model

def _load(model: Optional[str] = None) -> "spacy.Language":
    model = model or get_current_model()
    with _lock:
        if model in _cache:
            return _cache[model]
        nlp = spacy.load(model)
        _cache[model] = nlp
        return nlp

def finde_ner(text: str) -> Iterable[Tuple[int, int, str]]:
    nlp = _load()
    doc = nlp(text)
    for ent in doc.ents:
        yield (ent.start_char, ent.end_char, ent.label_)