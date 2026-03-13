from __future__ import annotations

import threading
from typing import Dict

import spacy

from core.einstellungen import NER_PRESETS, SPACY_MODELL


class SpacyModelManager:
    def __init__(self):
        self._cache: Dict[str, "spacy.Language"] = {}
        self._lock = threading.Lock()
        self._current_model = SPACY_MODELL

    def _resolve(self, name: str) -> str:
        if name in NER_PRESETS:
            return NER_PRESETS[name]
        return name

    def set_model(self, name: str) -> str:
        model = self._resolve(name)
        with self._lock:
            self._current_model = model
        return model

    def get_model(self) -> str:
        return self._current_model

    def load(self):
        model = self._current_model

        with self._lock:
            if model in self._cache:
                return self._cache[model]

            nlp = spacy.load(model)
            self._cache[model] = nlp
            return nlp


MODEL_MANAGER = SpacyModelManager()