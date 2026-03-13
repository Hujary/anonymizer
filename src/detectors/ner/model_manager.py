from __future__ import annotations

import threading
from typing import Dict

import spacy

from core.einstellungen import NER_PRESETS, SPACY_MODELL


class SpacyModelManager:
    def __init__(self):
        # Cache für bereits geladene spaCy Modelle
        self._cache: Dict[str, "spacy.Language"] = {}

        # Lock für threadsicheren Zugriff
        self._lock = threading.Lock()

        # Aktuell verwendetes Modell
        self._current_model = SPACY_MODELL

    def _resolve(self, name: str) -> str:
        # Preset-Namen auf echtes spaCy Modell auflösen
        if name in NER_PRESETS:
            return NER_PRESETS[name]
        return name

    def set_model(self, name: str) -> str:
        # Aktuelles Modell setzen (wird erst bei Bedarf geladen)
        model = self._resolve(name)

        with self._lock:
            self._current_model = model

        return model

    def get_model(self) -> str:
        # Aktuellen Modellnamen zurückgeben
        return self._current_model

    def load(self):
        # spaCy Modell laden (Lazy Loading + Cache)
        model = self._current_model

        with self._lock:
            # Wenn Modell bereits geladen → aus Cache zurückgeben
            if model in self._cache:
                return self._cache[model]

            # Modell laden und im Cache speichern
            nlp = spacy.load(model)
            self._cache[model] = nlp

            return nlp


# Globaler Model Manager
MODEL_MANAGER = SpacyModelManager()