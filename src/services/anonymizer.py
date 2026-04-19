from __future__ import annotations

import json
import hashlib
import hmac
from typing import Callable, Dict, List, Optional, Tuple, Any

from pipeline.anonymisieren import maskiere
from pipeline.validation import filter_effective_hits_for_masking
from services.session_manager import SessionManager


MaskingPhaseCallback = Callable[[str], None]


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
    on_phase: Optional[MaskingPhaseCallback] = None,
) -> Tuple[str, Dict[str, str], List[Any]]:
    if on_phase is not None:
        try:
            from detectors.ner.model_manager import MODEL_MANAGER
            if MODEL_MANAGER.is_current_model_loaded():
                on_phase("Maskierung")
            else:
                on_phase("NER-Initialisierung")
        except Exception:
            on_phase("Maskierung")

    masked, hits = maskiere(text, reversible=False, on_phase=on_phase)

    if not reversible:
        return masked, {}, hits

    if session_mgr is None:
        session_mgr = SessionManager()

    session_secret = session_mgr.get_or_create_active_session_secret()

    effective_hits = sorted(
        filter_effective_hits_for_masking(hits),
        key=lambda h: getattr(h, "start"),
    )

    parts: List[str] = []
    mapping: Dict[str, str] = {}
    pos = 0

    for h in effective_hits:
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

    return masked_with_ids, mapping, hits


def de_anonymize(text: str, mapping: Dict[str, str]) -> str:
    for k in sorted(mapping.keys(), key=lambda s: -len(s)):
        text = text.replace(k, mapping[k])
    return text


def mapping_to_json(mapping: Dict[str, str]) -> str:
    return json.dumps(mapping, ensure_ascii=False, indent=2)