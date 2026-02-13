# detectors/ner/ner_core.py

###     NER-Detektor (spaCy) mit umschaltbarem Modell, Cache + ORG/PER-Boost
### __________________________________________________________________________
#
#  Datei: detectors/ner/ner_core.py
#
#  - Unterstützt Modellumschaltung zur Laufzeit (Preset oder direkter Modellname)
#  - Thread-sicherer Zugriff auf Modellwechsel und Cache
#  - spaCy-Modelle werden einmalig geladen und im Speicher gehalten
#  - Liefert Character-Offsets + Label für Downstream-Pipeline (Masking)
#  - ORG-Boost für Rechtsformen via:
#      (1) EntityRuler (token-basiert, after="ner", overwrite_ents=True)
#      (2) Char-level Post-Boost (regex) auf doc.ents (Offsets bleiben korrekt)
#  - PER-Boost für Mentions via:
#      (3) Char-level Mention-Boost: "@Tobias" => PER("Tobias") (Offsets bleiben korrekt)
#
#  WICHTIGER FIX (Gating):
#    - Wenn config["ner_labels"] leer ist, liefert finde_ner() IMMER keine Treffer.
#    - Damit kann NER im UI effektiv "deaktiviert" werden, ohne dass irgendwo noch
#      spaCy durchläuft und Treffer (fälschlich) in der UI auftauchen.
#

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import spacy
from spacy.tokens import Doc, Span

from core import config
from core.einstellungen import NER_PRESETS, SPACY_MODELL


@dataclass(frozen=True)
class SpacyNerDetector:
    _cache: Dict[str, "spacy.Language"]
    _lock: threading.Lock
    _current_model: str

    @staticmethod
    def _org_legal_forms() -> List[str]:
        cfg = config.get("org_legal_forms", None)
        if isinstance(cfg, list):
            out: List[str] = []
            for x in cfg:
                s = str(x).strip().lower()
                if s:
                    out.append(s)
            if out:
                return out

        return [
            "gmbh",
            "ag",
            "kg",
            "ug",
            "gbr",
            "kgaa",
            "eg",
            "ev",
            "e.v.",
            "e.v",
            "e. v.",
            "verein",
            "mbh",
        ]

    @staticmethod
    def _resolve_model(name_or_preset: str) -> str:
        if name_or_preset in NER_PRESETS:
            return NER_PRESETS[name_or_preset]
        return name_or_preset

    def get_current_model(self) -> str:
        return self._current_model

    def set_spacy_model(self, name_or_preset: str) -> str:
        model = self._resolve_model(name_or_preset)
        with self._lock:
            object.__setattr__(self, "_current_model", model)
        return model

    def _add_entity_ruler_if_needed(self, nlp: "spacy.Language") -> None:
        if "entity_ruler" in nlp.pipe_names:
            return

        ruler = nlp.add_pipe("entity_ruler", after="ner", config={"overwrite_ents": True})

        forms = self._org_legal_forms()
        form_set = sorted(set([f.lower() for f in forms if f.strip()]))

        patterns: List[dict] = []

        patterns.append(
            {
                "label": "ORG",
                "pattern": [
                    {"TEXT": {"REGEX": r"^[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9&\-.]{1,}$"}},
                    {"LOWER": {"IN": form_set}},
                ],
            }
        )

        patterns.append(
            {
                "label": "ORG",
                "pattern": [
                    {"TEXT": {"REGEX": r"^[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9&\-.]{1,}$"}},
                    {
                        "OP": "*",
                        "TEXT": {
                            "REGEX": r"^(?:[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9&\-.]{1,}|&|und|\+|-)$"
                        },
                    },
                    {"LOWER": {"IN": form_set}},
                ],
            }
        )

        patterns.append(
            {
                "label": "ORG",
                "pattern": [
                    {"TEXT": {"REGEX": r"^[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9&\-.]{1,}$"}},
                    {"LOWER": {"IN": ["gmbh"]}},
                    {"TEXT": {"IN": ["&", "und"]}, "OP": "?"},
                    {"LOWER": "co", "OP": "?"},
                    {"TEXT": ".", "OP": "?"},
                    {"LOWER": {"IN": ["kg"]}},
                ],
            }
        )

        ruler.add_patterns(patterns)

    @staticmethod
    def _compile_org_regex(forms: List[str]) -> re.Pattern:
        norm: List[str] = []
        for f in forms:
            s = str(f).strip().lower()
            if not s:
                continue
            norm.append(s.replace(" ", ""))
        norm = sorted(set(norm))

        def tolerant_form(f: str) -> str:
            letters = [re.escape(ch) for ch in f if ch.isalnum()]
            if not letters:
                return re.escape(f)
            return r"\s*\.?\s*".join(letters) + r"\.?"

        forms_alt = r"(?:%s)" % "|".join(tolerant_form(f) for f in norm)

        name_token = r"[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9&\.\-\+]{1,}"
        connector = r"(?:&|und|\+|-)"
        co_group = r"(?:\s*(?:&|und)\s*Co\.?\s*)?"

        pattern = rf"""
            (?P<org>
                {name_token}
                (?:\s+(?:{name_token}|{connector}))*
                \s+{forms_alt}
                (?:{co_group}{forms_alt})?
            )
        """

        return re.compile(pattern, re.VERBOSE | re.IGNORECASE)

    @staticmethod
    def _compile_mention_regex() -> re.Pattern:
        return re.compile(
            r"(?<![\w.+-])@(?P<name>[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)\b"
        )

    @staticmethod
    def _merge_spans_prefer_longer(spans: List[Span]) -> List[Span]:
        if not spans:
            return []

        spans_sorted = sorted(spans, key=lambda s: (s.start_char, -(s.end_char - s.start_char)))
        out: List[Span] = []

        for s in spans_sorted:
            conflict_idx: Optional[int] = None
            for i, kept in enumerate(out):
                if not (s.end_char <= kept.start_char or kept.end_char <= s.start_char):
                    conflict_idx = i
                    break

            if conflict_idx is None:
                out.append(s)
                continue

            kept = out[conflict_idx]
            if (s.end_char - s.start_char) > (kept.end_char - kept.start_char):
                out[conflict_idx] = s

        out.sort(key=lambda s: s.start_char)
        return out

    def _boost_org_legalforms(self, doc: Doc) -> Doc:
        forms = self._org_legal_forms()
        rx = self._compile_org_regex(forms)

        text = doc.text
        extra: List[Span] = []

        for m in rx.finditer(text):
            start = m.start("org")
            end = m.end("org")

            if "\n" in text[start:end] or "\r" in text[start:end]:
                continue
            if end - start < 4:
                continue

            sp = doc.char_span(start, end, label="ORG", alignment_mode="contract")
            if sp is not None:
                extra.append(sp)

        if not extra:
            return doc

        doc.ents = tuple(self._merge_spans_prefer_longer(list(doc.ents) + extra))
        return doc

    def _boost_mentions(self, doc: Doc) -> Doc:
        rx = self._compile_mention_regex()
        text = doc.text
        extra: List[Span] = []

        for m in rx.finditer(text):
            start = m.start("name")
            end = m.end("name")

            left = text[max(0, m.start() - 64) : m.start()]
            right = text[m.end() : min(len(text), m.end() + 64)]
            if "@" in left and "." in right:
                continue

            sp = doc.char_span(start, end, label="PER", alignment_mode="contract")
            if sp is not None:
                extra.append(sp)

        if not extra:
            return doc

        doc.ents = tuple(self._merge_spans_prefer_longer(list(doc.ents) + extra))
        return doc

    def _load(self, model: Optional[str] = None) -> "spacy.Language":
        model = model or self.get_current_model()
        with self._lock:
            if model in self._cache:
                return self._cache[model]

            nlp = spacy.load(model)
            if "ner" in nlp.pipe_names:
                self._add_entity_ruler_if_needed(nlp)

            self._cache[model] = nlp
            return nlp

    def find(self, text: str) -> Iterable[Tuple[int, int, str]]:
        nlp = self._load()
        doc = nlp(text)

        doc = self._boost_org_legalforms(doc)
        doc = self._boost_mentions(doc)

        for ent in doc.ents:
            yield (ent.start_char, ent.end_char, ent.label_)


_DETECTOR = SpacyNerDetector(_cache={}, _lock=threading.Lock(), _current_model=SPACY_MODELL)


def get_current_model() -> str:
    return _DETECTOR.get_current_model()


def set_spacy_model(name_or_preset: str) -> str:
    return _DETECTOR.set_spacy_model(name_or_preset)


def finde_ner(text: str) -> Iterable[Tuple[int, int, str]]:
    labels = config.get("ner_labels", [])
    if not isinstance(labels, list) or not any(str(x).strip() for x in labels):
        return iter(())
    return _DETECTOR.find(text)