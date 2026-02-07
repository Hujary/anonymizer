from __future__ import annotations

import json
import hashlib
from typing import Tuple, Dict, List, Any
from pipeline.anonymisieren import maskiere


def _stable_token(label: str, value: str) -> str:
    h = hashlib.sha1((label + "::" + (value or "")).encode("utf-8")).hexdigest()[:8]
    return f"[{label}_{h}]"


def anonymize(text: str, reversible: bool = False) -> Tuple[str, Dict[str, str], List[Any]]:
    if not reversible:
        masked, hits = maskiere(text, reversible=False)
        return masked, {}, hits

    _, hits = maskiere(text, reversible=True)

    hits_sorted = sorted(hits, key=lambda h: getattr(h, "start"))

    parts: List[str] = []
    mapping: Dict[str, str] = {}
    pos = 0

    for h in hits_sorted:
        s = getattr(h, "start")
        e = getattr(h, "ende")
        label = getattr(h, "label").upper()

        parts.append(text[pos:s])

        original = text[s:e]

        tag = _stable_token(label, original)

        parts.append(tag)
        mapping[tag] = original
        pos = e

    parts.append(text[pos:])
    masked_with_ids = "".join(parts)

    return masked_with_ids, mapping, hits_sorted


def de_anonymize(text: str, mapping: Dict[str, str]) -> str:
    for k in sorted(mapping.keys(), key=lambda s: -len(s)):
        text = text.replace(k, mapping[k])
    return text


def mapping_to_json(mapping: Dict[str, str]) -> str:
    return json.dumps(mapping, ensure_ascii=False, indent=2)