from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import re


def find_occurrences(text: str, value: str) -> List[Tuple[int, int]]:
    # Treffer finden:
    # - Wenn value ein "Wort" ist (\w+), dann Word-Boundary Matching
    # - Sonst simples Substring-Matching
    if not value:
        return []
    if re.fullmatch(r"\w+", value):
        pattern = r"\b" + re.escape(value) + r"\b"
        res: List[Tuple[int, int]] = []
        for m in re.finditer(pattern, text):
            res.append((m.start(), m.end()))
        return res

    res: List[Tuple[int, int]] = []
    start = 0
    n = len(value)
    while True:
        idx = text.find(value, start)
        if idx == -1:
            break
        res.append((idx, idx + n))
        start = idx + 1
    return res


# Interne Span-Struktur für Maskierung
@dataclass(frozen=True)
class MaskSpan:
    start: int
    end: int
    token: str
    value: str


def build_spans(text: str, mapping: Dict[str, str]) -> List[MaskSpan]:
    # Mapping expandieren: jede (token->value)-Zeile wird zu allen Vorkommen im Text
    spans: List[MaskSpan] = []
    for token, value in mapping.items():
        if not value:
            continue
        for start, end in find_occurrences(text, value):
            spans.append(MaskSpan(start=start, end=end, token=token, value=value))
    return spans


def select_non_overlapping_spans(spans: List[MaskSpan], text_len: int) -> List[MaskSpan]:
    # Overlap-Resolution:
    # - längere Treffer bevorzugen
    # - anschließend nach Start sortieren
    spans_sorted = sorted(spans, key=lambda s: (-(s.end - s.start), s.start))
    used = [False] * text_len
    chosen: List[MaskSpan] = []

    for span in spans_sorted:
        if span.start < 0 or span.end > text_len or span.start >= span.end:
            continue
        overlap = any(used[i] for i in range(span.start, span.end))
        if overlap:
            continue
        for i in range(span.start, span.end):
            used[i] = True
        chosen.append(span)

    chosen.sort(key=lambda s: s.start)
    return chosen


def apply_spans(text: str, spans: List[MaskSpan]) -> str:
    # Non-overlapping Spans in einem Pass anwenden
    if not spans:
        return text
    parts: List[str] = []
    pos = 0
    for span in spans:
        if span.start > pos:
            parts.append(text[pos:span.start])
        parts.append(span.token)
        pos = span.end
    if pos < len(text):
        parts.append(text[pos:])
    return "".join(parts)


def mask_with_mapping(text: str, mapping: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
    # Maskiert Text und gibt nur Mapping-Einträge zurück, die tatsächlich genutzt wurden
    if not mapping:
        return text, {}

    spans = build_spans(text, mapping)
    if not spans:
        return text, {}

    chosen = select_non_overlapping_spans(spans, len(text))
    masked = apply_spans(text, chosen)

    used_mapping: Dict[str, str] = {}
    for span in chosen:
        used_mapping[span.token] = span.value

    return masked, used_mapping