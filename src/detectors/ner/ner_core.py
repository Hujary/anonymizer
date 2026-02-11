###     NER-Detektor (spaCy) mit umschaltbarem Modell und Cache
### __________________________________________________________________________
#
#  - Unterstützt Modellumschaltung zur Laufzeit (Preset oder direkter Modellname)
#  - Thread-sicherer Zugriff auf Modellwechsel und Cache
#  - spaCy-Modelle werden einmalig geladen und im Speicher gehalten
#  - Liefert Character-Offsets + Label für Downstream-Pipeline (Masking)

from __future__ import annotations
from typing import Iterable, Tuple, Dict, Optional
import threading
import spacy

# Default-Modell + Preset-Mapping
from core.einstellungen import SPACY_MODELL, NER_PRESETS

# Cache für bereits geladene spaCy-Modelle (verhindert mehrfaches Laden)
_cache: Dict[str, "spacy.Language"] = {}

# Lock für Thread-Sicherheit bei Modellwechsel und Cache-Zugriff
_lock = threading.Lock()

# Aktuell aktives spaCy-Modell (wird bei Laufzeitwechsel aktualisiert)
_current_model: str = SPACY_MODELL  



# Hilfsfunktion zum Auflösen von Presets auf konkrete Modellnamen
def _resolve_model(name_or_preset: str) -> str:
    if name_or_preset in NER_PRESETS:
        return NER_PRESETS[name_or_preset]
    return name_or_preset



# Gibt den aktuell gesetzten spaCy-Modellnamen zurück.
def get_current_model() -> str:
    return _current_model



# Setzt das aktive spaCy-Modell
def set_spacy_model(name_or_preset: str) -> str:
    global _current_model
    model = _resolve_model(name_or_preset)
    with _lock:
        _current_model = model
    return model



# Lädt ein spaCy-Modell aus dem Cache oder initialisiert es neu.
def _load(model: Optional[str] = None) -> "spacy.Language":
    model = model or get_current_model()
    with _lock:
        if model in _cache:
            return _cache[model]

        nlp = spacy.load(model)
        _cache[model] = nlp
        return nlp



# Führt Named-Entity-Recognition auf dem gegebenen Text aus.
def finde_ner(text: str) -> Iterable[Tuple[int, int, str]]:
    nlp = _load()
    doc = nlp(text)

    for ent in doc.ents:
        yield (ent.start_char, ent.end_char, ent.label_)