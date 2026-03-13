from __future__ import annotations

from typing import Iterable, List, Tuple

from core import config
from core.typen import Treffer
from .filters import clean_ner_hits
from .model_manager import MODEL_MANAGER


def get_current_model() -> str:
    return MODEL_MANAGER.get_model()


def set_spacy_model(name: str) -> str:
    return MODEL_MANAGER.set_model(name)


def _has_active_ner_labels() -> bool:
    labels = config.get("ner_labels", [])

    if not isinstance(labels, list):
        return False

    return any(str(x).strip() for x in labels)


def finde_ner_raw(text: str) -> List[Treffer]:
    nlp = MODEL_MANAGER.load()
    doc = nlp(text)

    hits: List[Treffer] = []

    print("\n==================== NER RAW ====================")
    print(f"TEXT: {text!r}")
    print("-------------------------------------------------")

    for ent in doc.ents:
        label = str(ent.label_).strip().upper()
        span_text = text[ent.start_char:ent.end_char]

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

    if not hits:
        print("RAW | keine spaCy-Treffer")

    print("=================================================\n")
    return hits


def finde_ner(text: str) -> Iterable[Tuple[int, int, str]]:
    if not _has_active_ner_labels():
        print("\n==================== NER ====================")
        print("NER deaktiviert: keine aktiven ner_labels")
        print("============================================\n")
        return iter(())

    raw_hits = finde_ner_raw(text)
    final_hits = clean_ner_hits(text, raw_hits)

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