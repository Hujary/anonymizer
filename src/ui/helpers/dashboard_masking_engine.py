from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re


def find_occurrences(text: str, value: str) -> List[Tuple[int, int]]:
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


def find_best_occurrence(
    text: str,
    value: str,
    anchor_start: int,
    anchor_ende: int,
) -> Optional[Tuple[int, int]]:
    occs = find_occurrences(text, value)
    if not occs:
        return None

    containing = [(s, e) for s, e in occs if s <= anchor_start and anchor_ende <= e]
    if containing:
        containing.sort(key=lambda x: (abs(x[0] - anchor_start), abs((x[1] - x[0]) - (anchor_ende - anchor_start))))
        return containing[0]

    overlapping = [(s, e) for s, e in occs if not (e <= anchor_start or anchor_ende <= s)]
    if overlapping:
        overlapping.sort(key=lambda x: (abs(x[0] - anchor_start), abs((x[1] - x[0]) - (anchor_ende - anchor_start))))
        return overlapping[0]

    occs.sort(key=lambda x: abs(x[0] - anchor_start))
    return occs[0]


@dataclass(frozen=True)
class MaskSpan:
    row_id: str
    start: int
    end: int
    token: str
    value: str


def select_non_overlapping_spans(spans: List[MaskSpan], text_len: int) -> List[MaskSpan]:
    spans_sorted = sorted(spans, key=lambda s: (-(s.end - s.start), s.start))
    used = [False] * text_len
    chosen: List[MaskSpan] = []

    for span in spans_sorted:
        if span.start < 0 or span.end > text_len or span.start >= span.end:
            continue

        if any(used[i] for i in range(span.start, span.end)):
            continue

        for i in range(span.start, span.end):
            used[i] = True

        chosen.append(span)

    chosen.sort(key=lambda s: s.start)
    return chosen


def apply_spans(text: str, spans: List[MaskSpan]) -> str:
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


def mapping_from_spans(spans: List[MaskSpan]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for span in spans:
        out[span.token] = span.value
    return out