from __future__ import annotations

from typing import Iterable, List, Tuple

from core import config
from core.typen import Treffer
from .filters import clean_ner_hits
from .model_manager import MODEL_MANAGER


def get_current_backend() -> str:
    return MODEL_MANAGER.get_backend()


def set_ner_backend(name: str) -> str:
    return MODEL_MANAGER.set_backend(name)


def get_current_model() -> str:
    return MODEL_MANAGER.get_model()


def set_spacy_model(name: str) -> str:
    current_backend = MODEL_MANAGER.get_backend()
    if current_backend != "spacy":
        MODEL_MANAGER.set_backend("spacy")
    return MODEL_MANAGER.set_model(name)


def set_flair_model(name: str) -> str:
    current_backend = MODEL_MANAGER.get_backend()
    if current_backend != "flair":
        MODEL_MANAGER.set_backend("flair")
    return MODEL_MANAGER.set_model(name)


def _has_active_ner_labels() -> bool:
    labels = config.get("ner_labels", [])
    if not isinstance(labels, list):
        return False
    return any(str(x).strip() for x in labels)


def _is_debug_enabled() -> bool:
    return bool(config.get("debug_ner_result", False))


def _normalize_label(label: str) -> str:
    raw = str(label or "").strip().upper()

    mapping = {
        "PER": "PER",
        "PERSON": "PER",
        "ORG": "ORG",
        "ORGANIZATION": "ORG",
        "LOC": "LOC",
        "LOCATION": "LOC",
        "GPE": "LOC",
        "MISC": "MISC",
    }

    return mapping.get(raw, raw)


def _finde_ner_raw_spacy(text: str) -> List[Treffer]:
    nlp = MODEL_MANAGER.load()
    doc = nlp(text)

    hits: List[Treffer] = []
    debug_enabled = _is_debug_enabled()

    if debug_enabled:
        print("\n==================== NER RAW ====================")
        print("BACKEND: spacy")
        print(f"MODEL: {MODEL_MANAGER.get_model()}")
        print(f"TEXT: {text!r}")
        print("-------------------------------------------------")

    for ent in doc.ents:
        label = _normalize_label(str(ent.label_))
        span_text = text[ent.start_char:ent.end_char]

        if debug_enabled:
            print(
                f"RAW | label={label:<10} "
                f"| start={ent.start_char:<4} "
                f"| ende={ent.end_char:<4} "
                f"| text={span_text!r}"
            )

        if not label:
            continue

        hits.append(
            Treffer(
                ent.start_char,
                ent.end_char,
                label,
                "ner",
                from_ner=True,
            )
        )

    if debug_enabled and not hits:
        print("RAW | keine spaCy-Treffer")

    if debug_enabled:
        print("=================================================\n")

    return hits


def _finde_ner_raw_flair(text: str) -> List[Treffer]:
    from flair.data import Sentence

    tagger = MODEL_MANAGER.load()
    sentence = Sentence(text)
    tagger.predict(sentence)

    hits: List[Treffer] = []
    debug_enabled = _is_debug_enabled()

    if debug_enabled:
        print("\n==================== NER RAW ====================")
        print("BACKEND: flair")
        print(f"MODEL: {MODEL_MANAGER.get_model()}")
        print(f"TEXT: {text!r}")
        print("-------------------------------------------------")

    for span in sentence.get_spans("ner"):
        if not span.labels:
            continue

        raw_label = str(span.labels[0].value)
        label = _normalize_label(raw_label)
        start = int(span.start_position)
        ende = int(span.end_position)
        span_text = text[start:ende]

        if debug_enabled:
            print(
                f"RAW | raw_label={raw_label:<10} "
                f"| label={label:<10} "
                f"| start={start:<4} "
                f"| ende={ende:<4} "
                f"| text={span_text!r}"
            )

        if not label:
            continue

        hits.append(
            Treffer(
                start,
                ende,
                label,
                "ner",
                from_ner=True,
            )
        )

    if debug_enabled and not hits:
        print("RAW | keine Flair-Treffer")

    if debug_enabled:
        print("=================================================\n")

    return hits


def finde_ner_raw(text: str) -> List[Treffer]:
    backend = MODEL_MANAGER.get_backend()

    if backend == "flair":
        return _finde_ner_raw_flair(text)

    return _finde_ner_raw_spacy(text)


def finde_ner(text: str) -> Iterable[Tuple[int, int, str]]:
    if not _has_active_ner_labels():
        return iter(())

    raw_hits = finde_ner_raw(text)
    final_hits = clean_ner_hits(text, raw_hits)

    if _is_debug_enabled():
        print("\n==================== NER FINAL ====================")

        for h in final_hits:
            print(
                f"FINAL | label={h.label:<10} "
                f"| start={h.start:<4} "
                f"| ende={h.ende:<4} "
                f"| source={h.source:<5} "
                f"| from_ner={h.from_ner!s:<5} "
                f"| from_regex={h.from_regex!s:<5} "
                f"| text={text[h.start:h.ende]!r}"
            )

        if not final_hits:
            print("FINAL | keine Treffer nach Filterung")

        print("===================================================\n")

    def _generator():
        for h in final_hits:
            yield (h.start, h.ende, h.label)

    return _generator()