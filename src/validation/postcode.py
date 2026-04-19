from __future__ import annotations

import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Set, Tuple

import pandas as pd

from validation.types import ValidationDecision


_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n+")
_SINGLE_WS_RE = re.compile(r"\s+")


def clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def load_valid_postcodes(path: str | Path) -> Set[str]:
    df = pd.read_csv(path, dtype={"postcode": str})
    if "postcode" not in df.columns:
        raise ValueError("CSV muss eine Spalte 'postcode' enthalten.")
    return set(df["postcode"].astype(str).str.zfill(5))


def _is_hard_punctuation(ch: str) -> bool:
    return ch in ".!?"


def _find_left_boundary(text: str, hit_start: int) -> int:
    if hit_start <= 0:
        return 0

    last_punct = -1
    idx = hit_start - 1
    while idx >= 0:
        if _is_hard_punctuation(text[idx]):
            last_punct = idx
            break
        idx -= 1

    para_start = 0
    for m in _PARAGRAPH_BREAK_RE.finditer(text):
        if m.end() <= hit_start:
            para_start = m.end()
        else:
            break

    return max(last_punct + 1, para_start)


def _find_right_boundary(text: str, hit_end: int) -> int:
    n = len(text)

    next_punct_end = n
    idx = hit_end
    while idx < n:
        if _is_hard_punctuation(text[idx]):
            next_punct_end = idx + 1
            break
        idx += 1

    para_end = n
    m = _PARAGRAPH_BREAK_RE.search(text, hit_end)
    if m is not None:
        para_end = m.start()

    return min(next_punct_end, para_end)


def _normalize_context_and_span(
    context: str,
    rel_start: int,
    rel_end: int,
) -> Tuple[str, int, int]:
    if rel_start < 0 or rel_end < rel_start or rel_end > len(context):
        raise ValueError("Ungültige relativen Span-Positionen für den Kontext.")

    out_chars: list[str] = []
    norm_start = None
    norm_end = None

    i = 0
    out_len = 0

    while i < len(context):
        if i == rel_start:
            norm_start = out_len
        if i == rel_end:
            norm_end = out_len

        ch = context[i]

        if ch.isspace():
            j = i
            while j < len(context) and context[j].isspace():
                if j == rel_start and norm_start is None:
                    norm_start = out_len
                if j == rel_end and norm_end is None:
                    norm_end = out_len
                j += 1

            if out_chars and out_chars[-1] != " ":
                out_chars.append(" ")
                out_len += 1

            i = j
            continue

        out_chars.append(ch)
        out_len += 1
        i += 1

    if norm_start is None:
        norm_start = out_len if rel_start == len(context) else 0
    if norm_end is None:
        norm_end = out_len if rel_end == len(context) else norm_start

    normalized = "".join(out_chars).strip()

    leading_trim = len("".join(out_chars)) - len("".join(out_chars).lstrip(" "))
    trailing_trimmed = "".join(out_chars).strip(" ")

    norm_start = max(0, norm_start - leading_trim)
    norm_end = max(norm_start, norm_end - leading_trim)

    if norm_end > len(trailing_trimmed):
        norm_end = len(trailing_trimmed)
    if norm_start > len(trailing_trimmed):
        norm_start = len(trailing_trimmed)

    return trailing_trimmed, norm_start, norm_end


def _extract_candidate_context(
    text: str,
    start: int,
    end: int,
) -> Tuple[str, int, int, int, int]:
    if start < 0 or end > len(text) or start >= end:
        raise ValueError("Ungültiger Treffer-Span.")

    context_start = _find_left_boundary(text, start)
    context_end = _find_right_boundary(text, end)

    context = text[context_start:context_end]
    rel_start = start - context_start
    rel_end = end - context_start

    normalized_context, norm_start, norm_end = _normalize_context_and_span(
        context,
        rel_start,
        rel_end,
    )

    return normalized_context, norm_start, norm_end, context_start, context_end


def build_model_input_from_span(
    context: str,
    start: int,
    end: int,
    placeholder: str = "[PLZ]",
) -> str:
    if start < 0 or end > len(context) or start >= end:
        raise ValueError("Ungültiger Span im Kontext.")

    return (
        context[:start]
        + f"<cand> {placeholder} </cand>"
        + context[end:]
    )


@dataclass
class PostcodeValidator:
    model: object
    threshold: float
    placeholder: str
    valid_postcodes: Set[str]
    unknown_postcode_malus: float = 0.10
    validator_name: str = "postcode_ml"

    @classmethod
    def from_pickle(
        cls,
        *,
        model_path: str | Path,
        postcode_reference_path: str | Path,
        unknown_postcode_malus: float = 0.10,
    ) -> "PostcodeValidator":
        model_path = Path(model_path)
        postcode_reference_path = Path(postcode_reference_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model-Datei nicht gefunden: {model_path}")

        if not postcode_reference_path.exists():
            raise FileNotFoundError(f"PLZ-Referenzdatei nicht gefunden: {postcode_reference_path}")

        with model_path.open("rb") as f:
            bundle = pickle.load(f)

        if not isinstance(bundle, dict):
            raise ValueError("Model-Bundle muss ein Dictionary sein.")
        if "model" not in bundle:
            raise ValueError("Model-Bundle enthält keinen Key 'model'.")
        if "threshold" not in bundle:
            raise ValueError("Model-Bundle enthält keinen Key 'threshold'.")
        if "placeholder" not in bundle:
            raise ValueError("Model-Bundle enthält keinen Key 'placeholder'.")

        model = bundle["model"]
        threshold = float(bundle["threshold"])
        placeholder = str(bundle["placeholder"])
        valid_postcodes = load_valid_postcodes(postcode_reference_path)

        return cls(
            model=model,
            threshold=threshold,
            placeholder=placeholder,
            valid_postcodes=valid_postcodes,
            unknown_postcode_malus=float(unknown_postcode_malus),
        )

    def validate(
        self,
        text: str,
        candidate: str,
        *,
        start: int | None = None,
        end: int | None = None,
        threshold_override: float | None = None,
    ) -> ValidationDecision:
        if not isinstance(text, str) or not text:
            raise ValueError("text darf nicht leer sein.")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError("candidate darf nicht leer sein.")

        if start is None or end is None:
            start = text.find(candidate)
            if start == -1:
                raise ValueError("candidate kommt im text nicht vor.")
            end = start + len(candidate)

        if start < 0 or end > len(text) or start >= end:
            raise ValueError("Ungültige start/end-Werte.")

        actual = text[start:end]
        if actual != candidate:
            raise ValueError(
                f"Kandidat stimmt nicht mit Textspan überein. Erwartet '{candidate}', gefunden '{actual}'."
            )

        effective_threshold = self.threshold if threshold_override is None else float(threshold_override)
        if effective_threshold < 0.0 or effective_threshold > 1.0:
            raise ValueError("threshold_override muss zwischen 0.0 und 1.0 liegen.")

        context_text, rel_start, rel_end, context_start, context_end = _extract_candidate_context(
            text,
            start,
            end,
        )
        model_input = build_model_input_from_span(
            context_text,
            rel_start,
            rel_end,
            placeholder=self.placeholder,
        )

        candidate_normalized = candidate.strip().zfill(5)

        proba = self.model.predict_proba([model_input])[0]
        raw_score = float(proba[1])

        in_reference = candidate_normalized in self.valid_postcodes

        adjustment = 0.0
        reason = "Kein Adjustment."

        if not in_reference:
            adjustment = -self.unknown_postcode_malus
            reason = "PLZ nicht in Referenzliste -> Malus angewendet."

        final_score = clamp_score(raw_score + adjustment)
        accepted = final_score >= effective_threshold

        return ValidationDecision(
            validator_name=self.validator_name,
            label="PLZ",
            candidate=candidate,
            accepted=accepted,
            score=final_score,
            threshold=effective_threshold,
            reason=reason,
            raw_score=raw_score,
            adjustment=adjustment,
            reference_hit=in_reference,
            context_text=context_text,
            model_input=model_input,
            context_start=context_start,
            context_end=context_end,
        )