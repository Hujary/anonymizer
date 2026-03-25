from __future__ import annotations

import importlib.util
import threading
from typing import Any, Dict

import spacy
from spacy.util import is_package

from core import config


SPACY_PRESETS = {
    "de_core_news_md": "de_core_news_md",
    "de_core_news_lg": "de_core_news_lg",
}

FLAIR_PRESETS = {
    "flair/ner-german-large": "flair/ner-german-large",
}


class NerModelManager:
    def __init__(self) -> None:
        self._spacy_cache: Dict[str, Any] = {}
        self._flair_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()

        backend = str(config.get("ner_backend", "spacy") or "spacy").strip().lower()
        if backend not in ("spacy", "flair"):
            backend = "spacy"
        self._current_backend = backend

        model = str(config.get("ner_model", "de_core_news_lg") or "").strip()
        if not model:
            model = "de_core_news_lg"
        self._current_model = self._resolve_model(backend, model)

    def _resolve_backend(self, backend: str) -> str:
        value = str(backend or "").strip().lower()
        if value not in ("spacy", "flair"):
            raise ValueError(f"Unsupported NER backend: {backend}")
        return value

    def _resolve_model(self, backend: str, model: str) -> str:
        raw = str(model or "").strip()

        if backend == "spacy":
            if raw in SPACY_PRESETS:
                return SPACY_PRESETS[raw]
            return raw or "de_core_news_lg"

        if raw in FLAIR_PRESETS:
            return FLAIR_PRESETS[raw]
        return raw or "flair/ner-german-large"

    def get_backend(self) -> str:
        with self._lock:
            return self._current_backend

    def set_backend(self, backend: str) -> str:
        value = self._resolve_backend(backend)

        with self._lock:
            self._current_backend = value

        config.set("ner_backend", value)
        return value

    def get_model(self) -> str:
        with self._lock:
            return self._current_model

    def set_model(self, model: str) -> str:
        with self._lock:
            backend = self._current_backend

        resolved = self._resolve_model(backend, model)

        with self._lock:
            self._current_model = resolved

        config.set("ner_model", resolved)
        return resolved

    def set_backend_and_model(self, backend: str, model: str) -> tuple[str, str]:
        resolved_backend = self._resolve_backend(backend)
        resolved_model = self._resolve_model(resolved_backend, model)

        with self._lock:
            self._current_backend = resolved_backend
            self._current_model = resolved_model

        config.set("ner_backend", resolved_backend)
        config.set("ner_model", resolved_model)
        return resolved_backend, resolved_model

    def is_loaded(self, backend: str, model: str) -> bool:
        resolved_backend = self._resolve_backend(backend)
        resolved_model = self._resolve_model(resolved_backend, model)

        with self._lock:
            if resolved_backend == "flair":
                return resolved_model in self._flair_cache
            return resolved_model in self._spacy_cache

    def is_current_model_loaded(self) -> bool:
        with self._lock:
            backend = self._current_backend
            model = self._current_model

            if backend == "flair":
                return model in self._flair_cache
            return model in self._spacy_cache

    def load(self) -> Any:
        backend = self.get_backend()
        model = self.get_model()

        if backend == "flair":
            return self._load_flair(model)

        return self._load_spacy(model)

    def _load_spacy(self, model: str) -> Any:
        with self._lock:
            if model in self._spacy_cache:
                return self._spacy_cache[model]

            nlp = spacy.load(model)
            self._spacy_cache[model] = nlp
            return nlp

    def _load_flair(self, model: str) -> Any:
        with self._lock:
            if model in self._flair_cache:
                return self._flair_cache[model]

        from flair.models import SequenceTagger

        tagger = SequenceTagger.load(model)

        with self._lock:
            self._flair_cache[model] = tagger

        return tagger

    def flair_available(self) -> bool:
        return importlib.util.find_spec("flair") is not None

    def spacy_model_installed(self, model_name: str) -> bool:
        try:
            return is_package(model_name)
        except Exception:
            return False

    def available_spacy_models(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []

        for model_name in SPACY_PRESETS.values():
            if self.spacy_model_installed(model_name):
                out.append((model_name, model_name))

        return out

    def available_flair_models(self) -> list[tuple[str, str]]:
        if not self.flair_available():
            return []

        return [(model_name, model_name) for model_name in FLAIR_PRESETS.values()]


MODEL_MANAGER = NerModelManager()