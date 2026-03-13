from __future__ import annotations

from typing import Iterable, List, Tuple

from core import config
from core.typen import Treffer
from .filters import clean_ner_hits
from .model_manager import MODEL_MANAGER


def get_current_model() -> str:
    # Gibt das aktuell gesetzte spaCy-Modell zurück
    return MODEL_MANAGER.get_model()


def set_spacy_model(name: str) -> str:
    # Setzt das gewünschte spaCy-Modell
    return MODEL_MANAGER.set_model(name)


def _has_active_ner_labels() -> bool:
    # Prüft, ob in der Konfiguration mindestens ein NER-Label aktiv ist
    labels = config.get("ner_labels", [])

    if not isinstance(labels, list):
        return False

    return any(str(x).strip() for x in labels)


def _is_debug_enabled() -> bool:
    # Prüft, ob die NER-Debugausgabe aktiviert ist
    return bool(config.get("debug_ner_result", False))


def finde_ner_raw(text: str) -> List[Treffer]:
    # Führt spaCy-NER auf dem Eingabetext aus und gibt rohe Treffer zurück
    nlp = MODEL_MANAGER.load()
    doc = nlp(text)

    hits: List[Treffer] = []
    debug_enabled = _is_debug_enabled()

    if debug_enabled:
        print("\n==================== NER RAW ====================")
        print(f"TEXT: {text!r}")
        print("-------------------------------------------------")

    for ent in doc.ents:
        label = str(ent.label_).strip().upper()
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


def finde_ner(text: str) -> Iterable[Tuple[int, int, str]]:
    # Führt die vollständige NER-Pipeline aus und gibt finale Treffer zurück
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
        # Gibt Treffer im bisherigen Rückgabeformat zurück
        for h in final_hits:
            yield (h.start, h.ende, h.label)

    return _generator()