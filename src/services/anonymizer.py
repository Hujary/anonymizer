from __future__ import annotations

import json
import hashlib
import hmac
from typing import Tuple, Dict, List, Any, Optional

from pipeline.anonymisieren import maskiere
from services.session_manager import SessionManager


def _stable_token(label: str, value: str, session_secret: str) -> str:
    msg = (label.upper() + "::" + (value or "")).encode("utf-8")
    key = session_secret.encode("utf-8")
    h = hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]
    return f"[{label.upper()}_{h}]"


def anonymize(
    text: str,
    reversible: bool = False,
    *,
    session_mgr: Optional[SessionManager] = None,
) -> Tuple[str, Dict[str, str], List[Any]]:
    if not reversible:
        masked, hits = maskiere(text, reversible=False)
        return masked, {}, hits

    if session_mgr is None:
        session_mgr = SessionManager()

    session_secret = session_mgr.get_or_create_active_session_secret()

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
        tag = _stable_token(label, original, session_secret)

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